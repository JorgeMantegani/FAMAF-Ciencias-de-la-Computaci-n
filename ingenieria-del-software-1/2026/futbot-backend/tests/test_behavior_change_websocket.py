import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.engine.state import Team
from app.models.behavior import Behavior
from app.models.match_player import MatchPlayer
from app.models.user import User
from app.services import match_runner
from app.services.auth import start_session
from scripts.demo_match import create_demo


@pytest.fixture
def demo(db):
    return create_demo(db)


def token_for(db, email):
    return start_session(db, db.scalar(select(User).where(User.email == email))).access_token


def connect(client, match_id):
    return client.websocket_connect(
        f"/api/matches/{match_id}/ws", headers={"origin": "http://localhost:5173"}
    )


def authenticate(socket, token):
    socket.send_json({"type": "auth", "token": token})
    return socket.receive_json()


@pytest.fixture
def live_engine(db, demo, monkeypatch):
    engine = match_runner.build_engine_from_db(db, demo.match_id, get_settings())
    engine.start()
    monkeypatch.setitem(match_runner._engines, demo.match_id, engine)
    monkeypatch.setitem(
        match_runner._match_club_teams,
        demo.match_id,
        {
            demo.club_ids[0]: Team.HOME,
            demo.club_ids[1]: Team.AWAY,
        },
    )
    yield engine
    engine.close()


@pytest.fixture
def own_behavior(db, demo):
    behavior = Behavior(
        club_id=demo.club_ids[0],
        name="Cambio en vivo",
        code="def behavior(player):\n    pass",
        is_preprogrammed=False,
    )
    db.add(behavior)
    db.commit()
    return behavior


def change_message(player_id, behavior_id):
    return {
        "action": "CHANGE_BEHAVIOR",
        "payload": {"playerId": player_id, "behaviorId": behavior_id},
    }


def open_ready(client, db, demo):
    """Abre el socket autenticado y consume los dos mensajes iniciales."""
    socket = connect(client, demo.match_id)
    socket.__enter__()
    assert authenticate(socket, token_for(db, demo.emails[0]))["type"] == "state"
    assert socket.receive_json()["type"] == "SUBSTITUTION_STATE"
    return socket


def test_change_behavior_is_confirmed_and_applies_on_next_tick(
    client, db, demo, live_engine, own_behavior
):
    player_id = demo.player_ids[0][0]
    previous = live_engine.behavior_ids[player_id]

    socket = open_ready(client, db, demo)
    try:
        socket.send_json(change_message(player_id, own_behavior.id))
        assert socket.receive_json() == {
            "event": "BEHAVIOR_CHANGED",
            "payload": {"playerId": player_id, "behaviorId": own_behavior.id},
        }
    finally:
        socket.__exit__(None, None, None)

    # Todavía no rige: queda encolado hasta el próximo tick.
    assert live_engine.behavior_ids[player_id] == previous
    assert live_engine._pending_behavior_changes == [(player_id, own_behavior.id)]

    live_engine._apply_pending_behavior_changes()  # lo que hace tick() al empezar
    assert live_engine.behavior_ids[player_id] == own_behavior.id


def test_unknown_behavior_is_rejected_and_socket_stays_open(
    client, db, demo, live_engine, own_behavior
):
    player_id = demo.player_ids[0][0]
    socket = open_ready(client, db, demo)
    try:
        socket.send_json(change_message(player_id, "no-existe"))
        error = socket.receive_json()
        assert error["type"] == "error"
        assert error["error_code"] == "BEHAVIOR_CHANGE_BEHAVIOR_UNAVAILABLE"
        assert live_engine._pending_behavior_changes == []

        # El socket sigue abierto: un pedido válido después funciona.
        socket.send_json(change_message(player_id, own_behavior.id))
        assert socket.receive_json()["event"] == "BEHAVIOR_CHANGED"
    finally:
        socket.__exit__(None, None, None)


def test_bench_player_is_rejected(client, db, demo, live_engine, own_behavior):
    bench_player_id = demo.player_ids[0][3]
    socket = open_ready(client, db, demo)
    try:
        socket.send_json(change_message(bench_player_id, own_behavior.id))
        error = socket.receive_json()
        assert error["type"] == "error"
        assert error["error_code"] == "BEHAVIOR_CHANGE_INVALID_PLAYER"
        assert live_engine._pending_behavior_changes == []
    finally:
        socket.__exit__(None, None, None)


def test_invalid_payload_is_rejected_and_socket_stays_open(
    client, db, demo, live_engine, own_behavior
):
    socket = open_ready(client, db, demo)
    try:
        socket.send_json({"action": "CHANGE_BEHAVIOR", "payload": {"playerId": 1}})
        error = socket.receive_json()
        assert error["error_code"] == "BEHAVIOR_CHANGE_INVALID_REQUEST"

        socket.send_json(change_message(demo.player_ids[0][0], own_behavior.id))
        assert socket.receive_json()["event"] == "BEHAVIOR_CHANGED"
    finally:
        socket.__exit__(None, None, None)


def test_match_without_engine_is_rejected(client, db, demo, own_behavior, monkeypatch):
    monkeypatch.delitem(match_runner._engines, demo.match_id, raising=False)
    with connect(client, demo.match_id) as socket:
        assert authenticate(socket, token_for(db, demo.emails[0]))["type"] == "state"
        socket.send_json(change_message(demo.player_ids[0][0], own_behavior.id))
        error = socket.receive_json()
        assert error["type"] == "error"
        assert error["error_code"] == "BEHAVIOR_CHANGE_MATCH_NOT_RUNNING"

def test_change_is_saved_as_current_behavior(client, db, demo, live_engine, own_behavior):
    player_id = demo.player_ids[0][0]
    socket = open_ready(client, db, demo)
    try:
        socket.send_json(change_message(player_id, own_behavior.id))
        assert socket.receive_json()['event'] == 'BEHAVIOR_CHANGED'
    finally:
        socket.__exit__(None, None, None)

    db.expire_all()
    saved = db.scalar(
        select(MatchPlayer.behavior_id).where(
            MatchPlayer.match_id == demo.match_id, MatchPlayer.player_id == player_id
        )
    )
    assert saved == own_behavior.id
