from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, decode_access_token
from app.core.config import get_settings
from app.engine.state import MatchPhase, Team, publish_engine_tick
from app.models.auth_session import AuthSession
from app.engine.live_state import match_states
from app.models.user import User
from app.models.match import Match
from app.models.room import Room
from app.services.auth import start_session
from app.services import match_runner
from app.services.match_state import publish_match_state
from app.schemas.match_state import MatchTick
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


def test_final_penalty_events_are_delivered_before_socket_closes(
    client, db, demo
):
    token = token_for(db, demo.emails[0])
    match_states.clear()
    with connect(client, demo.match_id) as socket:
        assert authenticate(socket, token)["status"] == 409
        publish_match_state(
            db, demo.match_id, make_tick(demo, 0), expected_revision=0
        )
        db.commit()
        assert socket.receive_json()["state"]["revision"] == 1

        final_events = [
            {"type": "PENALTY_SHOT_RESULT", "status": "missed"},
            {"type": "PENALTIES_TIEBREAK", "winner": "away"},
            {"type": "PENALTIES_FINISHED", "winner": "away"},
        ]
        final_data = make_tick(demo, 0).model_dump()
        final_data.update(
            status="finished",
            phase="FINISHED",
            current_time=demo.duration,
            penalty={
                "shooter_id": demo.player_ids[0][0],
                "goalkeeper_id": demo.player_ids[1][0],
                "score": {"home": 0, "away": 0},
                "attempts": {"home": 5, "away": 5},
                "seconds_remaining": 0,
                "winner_club_id": demo.club_ids[1],
            },
        )
        publish_engine_tick(
            db,
            demo.match_id,
            MatchTick.model_validate(final_data),
            expected_revision=1,
            penalty_winner_club_id=demo.club_ids[1],
            events=final_events,
        )

        received = [socket.receive_json() for _ in range(4)]
        assert received[:3] == final_events
        final_state = received[3]
        assert final_state["type"] == "state"
        assert final_state["state"]["status"] == "finished"
        assert final_state["state"]["penalty"]["winner_club_id"] == demo.club_ids[1]
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


def test_substitution_command_is_applied_and_events_reach_websocket(
    client, db, demo, monkeypatch
):
    token = token_for(db, demo.emails[0])
    engine = match_runner.build_engine_from_db(db, demo.match_id, get_settings())
    engine.start()
    monkeypatch.setitem(match_runner._engines, demo.match_id, engine)
    monkeypatch.setitem(match_runner._match_club_teams, demo.match_id, {
        demo.club_ids[0]: Team.HOME,
        demo.club_ids[1]: Team.AWAY,
    })

    try:
        with connect(client, demo.match_id) as socket:
            assert authenticate(socket, token)['type'] == 'state'
            initial_substitution_state = socket.receive_json()
            assert initial_substitution_state == {
                'type': 'SUBSTITUTION_STATE',
                'pendingSubstitution': None,
                'changesUsedThisPause': 0,
            }
            socket.send_json({
                'type': 'SUBSTITUTE_PLAYER',
                'outPlayerId': demo.player_ids[0][0],
                'inPlayerId': demo.player_ids[0][3],
            })
            scheduled = socket.receive_json()
            assert scheduled['type'] == 'SUBSTITUTION_SCHEDULED'
            assert engine.pending_substitution[Team.HOME] == {
                'outPlayerId': demo.player_ids[0][0],
                'inPlayerId': demo.player_ids[0][3],
            }

        with connect(client, demo.match_id) as reconnected:
            assert authenticate(reconnected, token)['type'] == 'state'
            assert reconnected.receive_json() == {
                'type': 'SUBSTITUTION_STATE',
                'pendingSubstitution': {
                    'outPlayerId': demo.player_ids[0][0],
                    'inPlayerId': demo.player_ids[0][3],
                },
                'changesUsedThisPause': 0,
            }

            engine.state.phase = MatchPhase.HYDRATION
            engine._apply_substitutions()
            applied = reconnected.receive_json()
            assert applied['type'] == 'SUBSTITUTION_APPLIED'
            assert demo.player_ids[0][3] in {
                player.id for player in engine.state.players
            }
            assert demo.player_ids[0][0] not in {
                player.id for player in engine.state.players
            }

            reconnected.send_json({
                'type': 'SUBSTITUTE_PLAYER',
                'outPlayerId': demo.player_ids[0][1],
                'inPlayerId': demo.player_ids[0][4],
            })
            rejected = reconnected.receive_json()
            assert rejected['type'] == 'error'
            assert rejected['error_code'] == 'SUBSTITUTION_LIMIT_REACHED'
            assert rejected['message'] == 'Solo se permite 1 cambio por pausa'

        with connect(client, demo.match_id) as reconnected_after_change:
            assert authenticate(reconnected_after_change, token)['type'] == 'state'
            assert reconnected_after_change.receive_json() == {
                'type': 'SUBSTITUTION_STATE',
                'pendingSubstitution': None,
                'changesUsedThisPause': 1,
            }
    finally:
        engine.close()


def test_substitution_service_rejections_include_error_codes(demo, monkeypatch):
    monkeypatch.delitem(match_runner._engines, demo.match_id, raising=False)
    unavailable = match_runner.request_match_substitution(
        demo.match_id, demo.club_ids[0], "out", "in"
    )
    assert unavailable["error_code"] == "SUBSTITUTION_ENGINE_UNAVAILABLE"

    monkeypatch.setitem(match_runner._engines, demo.match_id, object())
    not_a_participant = match_runner.request_match_substitution(
        demo.match_id, demo.club_ids[0], "out", "in"
    )
    assert not_a_participant["error_code"] == "SUBSTITUTION_CLUB_NOT_IN_MATCH"


def test_penalty_snapshot_includes_active_shot_data(db, demo):
    engine = match_runner.build_engine_from_db(db, demo.match_id, get_settings())
    try:
        engine._start_penalties()
        engine._penalty_ticks = 3
        roster = list(
            db.scalars(
                select(match_runner.MatchPlayer.player_id).where(
                    match_runner.MatchPlayer.match_id == demo.match_id
                )
            )
        )
        club_of = {Team.HOME: demo.club_ids[0], Team.AWAY: demo.club_ids[1]}

        tick = match_runner.capture_tick(engine, roster, club_of)

        assert tick.status == "paused"
        assert tick.phase == "PENALTIES"
        assert str(tick.penalty.shooter_id) == engine._penalty_shooter.id
        assert str(tick.penalty.goalkeeper_id) == engine._penalty_goalkeeper.id
        assert tick.penalty.score.model_dump() == {"home": 0, "away": 0}
        assert tick.penalty.seconds_remaining == max(
            0, 10 - engine._penalty_ticks * engine.dt
        )
    finally:
        engine.close()


def test_engine_reads_shootout_setting_from_league_room(db, demo):
    db.get(Room, demo.room_id).has_penalty_shootout = True
    db.commit()

    engine = match_runner.build_engine_from_db(db, demo.match_id, get_settings())
    try:
        assert engine.has_penalty_shootout is True
    finally:
        engine.close()


def test_disallowed_origin_is_rejected(client, demo):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f'/api/matches/{demo.match_id}/ws', headers={'origin': 'https://untrusted.example'}):
            pass
