from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, decode_access_token
from app.models.auth_session import AuthSession
from app.engine.live_state import match_states
from app.models.user import User
from app.services.auth import start_session
from app.services.match_state import publish_match_state
from scripts.demo_match import create_demo, make_tick


@pytest.fixture
def demo(db):
    return create_demo(db)


def token_for(db, email):
    return start_session(db, db.scalar(select(User).where(User.email == email))).access_token


def connect(client, match_id):
    return client.websocket_connect(f'/api/matches/{match_id}/ws', headers={'origin': 'http://localhost:5173'})


def authenticate(socket, token):
    socket.send_json({'type': 'auth', 'token': token})
    return socket.receive_json()


def test_both_clubs_receive_broadcast_without_commit_and_reconnect_to_latest(client, db, engine, demo):
    tokens = [token_for(db, email) for email in demo.emails]
    with connect(client, demo.match_id) as home, connect(client, demo.match_id) as away:
        initial = authenticate(home, tokens[0])
        assert initial == authenticate(away, tokens[1])
        assert initial['type'] == 'state'
        # El motor puede publicar desde otro hilo, sin commit ni escritura de estado.
        def publish():
            with Session(engine) as writer:
                publish_match_state(writer, demo.match_id, make_tick(demo, 40), expected_revision=1)
        with ThreadPoolExecutor() as executor:
            executor.submit(publish).result(timeout=10)
        updated = home.receive_json()
        assert updated == away.receive_json()
        assert updated['state']['score'] == {'home': 1, 'away': 0}
        assert updated['state']['revision'] == 2
    with connect(client, demo.match_id) as reopened:
        assert authenticate(reopened, tokens[0]) == updated


@pytest.mark.parametrize('case,status', [('invalid', 401), ('outsider', 403), ('missing', 404), ('bad_id', 422)])
def test_websocket_rejects_invalid_access(client, db, demo, login_user, case, status):
    token = token_for(db, demo.emails[0])
    match_id = demo.match_id
    if case == 'invalid':
        token = 'invalid'
    elif case == 'outsider':
        token = start_session(db, login_user).access_token
    elif case == 'missing':
        match_id = str(uuid4())
    else:
        match_id = 'not-a-uuid'
    with connect(client, match_id) as socket:
        assert authenticate(socket, token)['status'] == status
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_waiting_socket_receives_first_state_and_final_state(client, db, demo):
    token = token_for(db, demo.emails[0])
    match_states.clear()
    with connect(client, demo.match_id) as socket:
        assert authenticate(socket, token)['status'] == 409
        publish_match_state(db, demo.match_id, make_tick(demo, 0), expected_revision=0)
        db.commit()
        assert socket.receive_json()['state']['revision'] == 1
        publish_match_state(db, demo.match_id, make_tick(demo, demo.duration), expected_revision=1)
        db.commit()
        assert socket.receive_json()['state']['status'] == 'finished'
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
        assert closed.value.code == 1000


def test_logout_revokes_open_socket(client, db, demo):
    token = token_for(db, demo.emails[0])
    with connect(client, demo.match_id) as socket:
        assert authenticate(socket, token)['type'] == 'state'
        assert client.post('/api/auth/logout', headers={'Authorization': f'Bearer {token}'}).status_code == 204
        assert socket.receive_json()['status'] == 401


def test_heartbeat_does_not_poll_state_and_token_expiry_closes_socket(client, db, demo, monkeypatch):
    import app.ws.matches as stream
    token = token_for(db, demo.emails[0])
    claims = decode_access_token(token)
    token = create_access_token(claims['sub'], claims['sid'], expires_at=datetime.now(timezone.utc) + timedelta(seconds=4))
    monkeypatch.setattr(stream, 'HEARTBEAT_SECONDS', 0.1)
    reads = []
    original = stream.read_authorized_state
    def read(*args):
        reads.append(1)
        return original(*args)
    monkeypatch.setattr(stream, 'read_authorized_state', read)
    with connect(client, demo.match_id) as socket:
        assert authenticate(socket, token)['type'] == 'state'
        for _ in range(3):
            assert socket.receive_json() == {'type': 'ping'}
            socket.send_json({'type': 'pong'})
        assert len(reads) == 1
        while True:
            message = socket.receive_json()
            if message['type'] == 'error':
                assert message['status'] == 401
                break
            socket.send_json({'type': 'pong'})


def test_disallowed_origin_is_rejected(client, demo):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f'/api/matches/{demo.match_id}/ws', headers={'origin': 'https://untrusted.example'}):
            pass
