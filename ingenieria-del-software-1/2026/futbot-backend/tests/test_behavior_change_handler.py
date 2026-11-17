import pytest

from app.db.base import ahora_utc
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import Team
from app.models.behavior import Behavior
from app.ws.behavior_change import handle_change_behavior


class Cfg:
    behavior_timeout_seconds = 0.05
    match_tick_rate = 10
    friendly_match_duration_seconds = 8


class FakeSocket:
    """Socket falso: guarda lo que se envía y registra si alguien lo cerró."""

    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_json(self, message):
        self.sent.append(message)

    async def close(self, *args, **kwargs):
        self.closed = True


def specs(prefix):
    return [PlayerSpec(f"{prefix}{i}", 60, 60, 60, 60, 60) for i in range(3)]


def make_behavior(db, club_id, name="Mi comportamiento", deleted=False):
    behavior = Behavior(
        club_id=club_id,
        name=name,
        code="def behavior(player):\n    pass",
        is_preprogrammed=club_id is None,
        deleted_at=ahora_utc() if deleted else None,
    )
    db.add(behavior)
    db.commit()
    return behavior


@pytest.fixture
def match_engine(club, other_club):
    field = FieldConfig()
    state = create_initial_state(field, specs("h"), specs("a"))
    schedule = build_schedule(8, 10, hydration_seconds=1, halftime_seconds=2)
    eng = MatchEngine(
        state,
        field,
        Cfg(),
        {p.id: "b" for p in state.players},
        schedule=schedule,
        realtime=False,
        club_ids={Team.HOME: club.id, Team.AWAY: other_club.id},
    )
    yield eng
    eng.close()


@pytest.fixture
def socket():
    return FakeSocket()


@pytest.mark.asyncio
async def test_valid_change_is_queued_and_confirmed(db, club, match_engine, socket):
    behavior = make_behavior(db, club.id)
    payload = {"playerId": "h0", "behaviorId": behavior.id}

    await handle_change_behavior(socket, db.get_bind(), match_engine, club.id, payload, "match-1")

    assert socket.sent == [
        {"event": "BEHAVIOR_CHANGED", "payload": {"playerId": "h0", "behaviorId": behavior.id}}
    ]
    assert match_engine._pending_behavior_changes == [("h0", behavior.id)]
    assert match_engine.behavior_ids["h0"] == "b"  # todavía no rige: falta el tick


@pytest.mark.asyncio
async def test_preprogrammed_behavior_is_accepted(
    db, club, match_engine, socket, comportamiento_prueba
):
    payload = {"playerId": "h0", "behaviorId": comportamiento_prueba.id}

    await handle_change_behavior(socket, db.get_bind(), match_engine, club.id, payload, "match-1")

    assert socket.sent[0]["event"] == "BEHAVIOR_CHANGED"


@pytest.mark.asyncio
async def test_behavior_of_other_club_is_rejected(db, club, other_club, match_engine, socket):
    behavior = make_behavior(db, other_club.id)
    payload = {"playerId": "h0", "behaviorId": behavior.id}

    await handle_change_behavior(socket, db.get_bind(), match_engine, club.id, payload, "match-1")

    assert socket.sent[0]["type"] == "error"
    assert socket.sent[0]["error_code"] == "BEHAVIOR_CHANGE_BEHAVIOR_UNAVAILABLE"
    assert match_engine._pending_behavior_changes == []


@pytest.mark.asyncio
async def test_deleted_behavior_is_rejected(db, club, match_engine, socket):
    behavior = make_behavior(db, club.id, deleted=True)
    payload = {"playerId": "h0", "behaviorId": behavior.id}

    await handle_change_behavior(socket, db.get_bind(), match_engine, club.id, payload, "match-1")

    assert socket.sent[0]["error_code"] == "BEHAVIOR_CHANGE_BEHAVIOR_UNAVAILABLE"
    assert match_engine._pending_behavior_changes == []


@pytest.mark.asyncio
async def test_player_of_other_team_is_rejected(db, club, match_engine, socket):
    behavior = make_behavior(db, club.id)
    payload = {"playerId": "a0", "behaviorId": behavior.id}

    await handle_change_behavior(socket, db.get_bind(), match_engine, club.id, payload, "match-1")

    assert socket.sent[0]["error_code"] == "BEHAVIOR_CHANGE_INVALID_PLAYER"
    assert match_engine._pending_behavior_changes == []


@pytest.mark.asyncio
async def test_club_that_does_not_play_is_rejected(db, match_engine, socket, comportamiento_prueba):
    payload = {"playerId": "h0", "behaviorId": comportamiento_prueba.id}

    await handle_change_behavior(socket, db.get_bind(), match_engine, "club-ajeno", payload, "match-1")

    assert socket.sent[0]["type"] == "error"
    assert socket.sent[0]["error_code"] == "BEHAVIOR_CHANGE_INVALID_PLAYER"
    assert match_engine._pending_behavior_changes == []


@pytest.mark.asyncio
async def test_match_not_running_is_rejected(db, club, socket):
    behavior = make_behavior(db, club.id)
    payload = {"playerId": "h0", "behaviorId": behavior.id}

    await handle_change_behavior(socket, db.get_bind(), None, club.id, payload, "match-1")

    ["error_code"] == "BEHAVIOR_CHANGE_MATCH_NOT_RUNNING"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        None,
        "texto",
        {},
        {"playerId": "h0"},
        {"behaviorId": "x"},
        {"playerId": 1, "behaviorId": 10},
    ],
)
async def test_invalid_payload_is_rejected(db, club, match_engine, socket, payload):
    await handle_change_behavior(socket, db.get_bind(), match_engine, club.id, payload, "match-1")

    assert socket.sent[0]["error_code"] == "BEHAVIOR_CHANGE_INVALID_REQUEST"
    assert match_engine._pending_behavior_changes == []


@pytest.mark.asyncio
async def test_rejection_does_not_close_the_socket(db, club, match_engine, socket):
    payload = {"playerId": "a0", "behaviorId": "no-existe"}

    await handle_change_behavior(socket, db.get_bind(), match_engine, club.id, payload, "match-1")

    assert socket.sent[0]["type"] == "error"
    assert socket.closed is False

@pytest.mark.asyncio
async def test_behavior_with_invalid_code_is_rejected(db, club, match_engine, socket):
    behavior = make_behavior(db, club.id)
    behavior.code = "esto no es python"
    db.commit()
    payload = {"playerId": "h0", "behaviorId": behavior.id}

    await handle_change_behavior(socket, db.get_bind(), match_engine, club.id, payload, "match-1")

    assert socket.sent[0]["error_code"] == "BEHAVIOR_CHANGE_BEHAVIOR_INVALID"
    assert match_engine._pending_behavior_changes == []
