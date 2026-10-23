import time
import pytest

from app.engine.action import NULL_ACTION
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import Vec2
from app.behaviors import executor 
from app.schemas.coord import Coord

class Cfg:
    behavior_timeout_seconds = 0.05
    match_tick_rate = 15
    friendly_match_duration_seconds = 300


def specs(prefix):
    return [PlayerSpec(f"{prefix}{i}", 60, 60, 60, 60, 60) for i in range(3)]


@pytest.fixture
def engine():
    field = FieldConfig()
    state = create_initial_state(field, specs("h"), specs("a"))
    eng = MatchEngine(state, field, Cfg(), {p.id: "b" for p in state.players})
    yield eng
    eng.close()


@pytest.mark.asyncio
async def test_normal_bots_produce_actions(engine, monkeypatch):
    def fake(pid, ctx):
        ctx.apply_movement(pid, Coord(x=10, y=10))     # Coord: importalo
    monkeypatch.setattr(executor, "ejecutar_comportamiento", fake)

    actions = await engine._collect_actions()
    assert all(a.move_to == Vec2(10, 10) for a in actions.values())


@pytest.mark.asyncio
async def test_raising_bot_gets_null_action(engine, monkeypatch):
    def fake(pid, ctx):
        if pid == "h0":
            raise RuntimeError("boom")
        ctx.apply_movement(pid, Coord(x=1, y=1))
    monkeypatch.setattr(executor, "ejecutar_comportamiento", fake)

    actions = await engine._collect_actions()
    assert actions["h0"] is NULL_ACTION
    assert actions["h1"].move_to == Vec2(1, 1)         # los demás siguen


@pytest.mark.asyncio
async def test_slow_bot_does_not_freeze_tick(engine, monkeypatch):
    def fake(pid, ctx):
        if pid == "h0":
            time.sleep(0.5)
        ctx.apply_movement(pid, Coord(x=1, y=1))
    monkeypatch.setattr(executor, "ejecutar_comportamiento", fake)

    t0 = time.monotonic()
    actions = await engine._collect_actions()
    elapsed = time.monotonic() - t0

    assert elapsed < 0.2
    assert actions["h0"] is NULL_ACTION
    assert actions["h1"].move_to == Vec2(1, 1)


@pytest.mark.asyncio
async def test_busy_bot_is_not_relaunched(engine, monkeypatch):
    calls = {"h0": 0}

    def fake(pid, ctx):
        if pid == "h0":
            calls["h0"] += 1
            time.sleep(0.3)
    monkeypatch.setattr(executor, "ejecutar_comportamiento", fake)

    await engine._collect_actions()
    await engine._collect_actions()      # h0 sigue ocupado del tick anterior
    assert calls["h0"] == 1