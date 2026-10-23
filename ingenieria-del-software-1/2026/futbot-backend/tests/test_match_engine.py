import pytest

from app.behaviors import executor
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import MatchPhase as P, Team, Vec2


class Cfg:
    behavior_timeout_seconds = 0.05
    match_tick_rate = 10
    friendly_match_duration_seconds = 8


def specs(prefix):
    return [PlayerSpec(f"{prefix}{i}", 60, 60, 60, 60, 60) for i in range(3)]


@pytest.fixture
def make_engine(monkeypatch):
    monkeypatch.setattr(executor, "ejecutar_comportamiento", lambda pid, ctx: None)
    engines = []

    def _make(on_finish=None):
        field = FieldConfig()
        state = create_initial_state(field, specs("h"), specs("a"))
        # 8 s a 10 tps = 20 ticks por periodo; hidratación 10 ticks, entretiempo 20
        sched = build_schedule(8, 10, hydration_seconds=1, halftime_seconds=2)
        eng = MatchEngine(state, field, Cfg(), {p.id: "b" for p in state.players},
                          schedule=sched, on_finish=on_finish, realtime=False)
        engines.append(eng)
        return eng

    yield _make
    for e in engines:
        e.close()


async def play_until_finished(eng, limit=1000):
    eng.start()
    phases = []
    for _ in range(limit):
        if eng.state.phase == P.FINISHED:
            break
        phases.append(eng.state.phase)
        await eng.tick()
    return phases


# ---------- Reloj ----------

@pytest.mark.asyncio
async def test_clock_advances_each_tick(make_engine):
    eng = make_engine()
    eng.start()
    for _ in range(5):
        await eng.tick()
    assert eng.state.tick_count == 5
    assert eng.state.play_ticks == 5
    assert eng.state.phase_tick == 5


# ---------- Fases ----------

@pytest.mark.asyncio
async def test_phase_sequence_and_totals(make_engine):
    eng = make_engine()
    phases = await play_until_finished(eng)

    collapsed = [p for i, p in enumerate(phases) if i == 0 or p != phases[i - 1]]
    assert collapsed == [P.PLAY, P.HYDRATION, P.PLAY, P.HALFTIME,
                         P.PLAY, P.HYDRATION, P.PLAY]
    assert eng.state.phase == P.FINISHED
    assert eng.state.play_ticks == 80                 # 4 periodos x 20
    assert eng.state.tick_count == 80 + 10 + 20 + 10  # + pausas


@pytest.mark.asyncio
async def test_transition_happens_on_exact_tick(make_engine):
    eng = make_engine()
    eng.start()
    for _ in range(19):
        await eng.tick()
    assert eng.state.phase == P.PLAY and eng.state.period == 1
    await eng.tick()                                   # tick 20: último de P1
    assert eng.state.phase == P.HYDRATION
    assert eng.state.phase_tick == 0


@pytest.mark.asyncio
async def test_play_clock_and_physics_frozen_during_pause(make_engine):
    eng = make_engine()
    eng.start()
    for _ in range(20):
        await eng.tick()                               # entra en HYDRATION
    eng.state.ball.pos = Vec2(30, 20)
    eng.state.ball.vel = Vec2(10, 0)
    before = eng.state.play_ticks
    await eng.tick()
    assert eng.state.play_ticks == before
    assert eng.state.ball.pos == Vec2(30, 20)          # no se movió
    assert eng.state.tick_count == 21


# ---------- Goles ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("pos,vel,scorer", [
    (Vec2(104.8, 34), Vec2(20, 0), Team.HOME),
    (Vec2(0.2, 34), Vec2(-20, 0), Team.AWAY),
])
async def test_goal_updates_score_and_resets(make_engine, pos, vel, scorer):
    eng = make_engine()
    eng.start()
    eng.state.ball.pos, eng.state.ball.vel = pos, vel
    kickoff = [p.pos for p in eng.state.players]
    eng.state.players[0].pos = Vec2(60, 10)            # desordeno a alguien

    await eng.tick()

    assert eng.state.score[scorer] == 1
    assert sum(eng.state.score.values()) == 1
    assert eng.state.ball.pos == eng.field.center
    assert eng.state.ball.vel == Vec2()
    assert [p.pos for p in eng.state.players] == kickoff


# ---------- Cierre y tolerancia a fallos ----------

@pytest.mark.asyncio
async def test_full_match_runs_and_notifies(make_engine):
    received = []

    async def on_finish(state):
        received.append(state.score.copy())

    eng = make_engine(on_finish=on_finish)
    await eng.run()
    assert eng.state.phase == P.FINISHED
    assert received == [{Team.HOME: 0, Team.AWAY: 0}]


@pytest.mark.asyncio
async def test_failing_on_finish_does_not_break_close(make_engine):
    async def boom(state):
        raise RuntimeError("db caída")

    eng = make_engine(on_finish=boom)
    await eng.run()                                    # no debe lanzar
    assert eng.state.phase == P.FINISHED


@pytest.mark.asyncio
async def test_raising_bot_does_not_freeze_match(make_engine, monkeypatch):
    def bad(pid, ctx):
        raise RuntimeError("boom")
    monkeypatch.setattr(executor, "ejecutar_comportamiento", bad)

    eng = make_engine()
    await eng.run()
    assert eng.state.phase == P.FINISHED
    assert eng.state.play_ticks == 80
    
@pytest.mark.asyncio
async def test_goal_event_records_author_and_second(make_engine):
    eng = make_engine()
    eng.start()
    eng.state.ball.pos, eng.state.ball.vel = Vec2(104.8, 34), Vec2(20, 0)
    eng.state.ball.last_kicker_id = "h0"
    await eng.tick()
    g = eng.state.goals[0]
    assert (g.team, g.player_id, g.second) == (Team.HOME, "h0", 0)


@pytest.mark.asyncio
async def test_own_goal_has_no_author(make_engine):
    eng = make_engine()
    eng.start()
    eng.state.ball.pos, eng.state.ball.vel = Vec2(104.8, 34), Vec2(20, 0)
    eng.state.ball.last_kicker_id = "a0"       # el rival fue el último en tocarla
    await eng.tick()
    assert eng.state.goals[0].player_id is None
    assert eng.state.score[Team.HOME] == 1