import pytest

from app.behaviors import executor
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import Team


class Cfg:
    behavior_timeout_seconds = 0.05
    match_tick_rate = 10
    friendly_match_duration_seconds = 8


HOME_CLUB = "club-home"
AWAY_CLUB = "club-away"


def specs(prefix):
    return [PlayerSpec(f"{prefix}{i}", 60, 60, 60, 60, 60) for i in range(3)]


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(executor, "ejecutar_comportamiento", lambda pid, ctx: None)
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
        club_ids={Team.HOME: HOME_CLUB, Team.AWAY: AWAY_CLUB},
    )
    eng.start()
    yield eng
    eng.close()


@pytest.mark.asyncio
async def test_behavior_change_applies_on_next_tick(engine):
    engine.request_behavior_change(HOME_CLUB, "h0", "nuevo")
    assert engine.behavior_ids["h0"] == "b"  # todavía no cambió
    await engine.tick()
    assert engine.behavior_ids["h0"] == "nuevo"


@pytest.mark.asyncio
async def test_change_only_affects_requested_player(engine):
    engine.request_behavior_change(HOME_CLUB, "h0", "nuevo")
    await engine.tick()
    assert engine.behavior_ids["h1"] == "b"
    assert engine.behavior_ids["a0"] == "b"


@pytest.mark.asyncio
async def test_last_request_wins(engine):
    engine.request_behavior_change(HOME_CLUB, "h0", "uno")
    engine.request_behavior_change(HOME_CLUB, "h0", "dos")
    await engine.tick()
    assert engine.behavior_ids["h0"] == "dos"


@pytest.mark.asyncio
async def test_pending_changes_are_cleared_after_tick(engine):
    engine.request_behavior_change(HOME_CLUB, "h0", "nuevo")
    await engine.tick()
    engine.behavior_ids["h0"] = "otro"  # algo lo cambia por fuera
    await engine.tick()
    assert engine.behavior_ids["h0"] == "otro"  # el pedido viejo no se reaplica


def test_club_not_in_match_is_rejected(engine):
    with pytest.raises(ValueError):
        engine.request_behavior_change("club-ajeno", "h0", "nuevo")


def test_player_of_other_team_is_rejected(engine):
    with pytest.raises(ValueError):
        engine.request_behavior_change(HOME_CLUB, "a0", "nuevo")


def test_unknown_player_is_rejected(engine):
    with pytest.raises(ValueError):
        engine.request_behavior_change(HOME_CLUB, "no-existe", "nuevo")


def test_rejected_request_does_not_change_anything(engine):
    with pytest.raises(ValueError):
        engine.request_behavior_change(HOME_CLUB, "a0", "nuevo")
    assert engine._pending_behavior_changes == []
