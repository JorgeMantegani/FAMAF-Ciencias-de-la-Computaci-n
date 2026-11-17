import pytest

from app.behaviors import executor
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import MatchPhase as P, PlayerState, Team, Vec2


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

    def _make(on_finish=None, has_penalty_shootout=False):
        field = FieldConfig()
        state = create_initial_state(field, specs("h"), specs("a"))
        # 8 s a 10 tps = 20 ticks por periodo; hidratación 10 ticks, entretiempo 20
        sched = build_schedule(8, 10, hydration_seconds=1, halftime_seconds=2)
        eng = MatchEngine(state, field, Cfg(), {p.id: "b" for p in state.players},
                          schedule=sched, on_finish=on_finish, realtime=False,
                          has_penalty_shootout=has_penalty_shootout)
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


def register_home_substitute(eng, player_id="h3"):
    eng.set_substitute(
        Team.HOME,
        player_id,
        PlayerState(
            id=player_id,
            team=Team.HOME,
            pos=Vec2(),
            speed=60,
            control=60,
            strength=60,
            power=60,
            agility=60,
        ),
    )


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
async def test_tied_match_enters_penalties_when_enabled(make_engine):
    eng = make_engine(has_penalty_shootout=True)
    eng.start()
    eng.state.score[Team.HOME] = eng.state.score[Team.AWAY] = 1
    eng._segment_index = len(eng.schedule) - 1
    eng.state.phase = P.PLAY
    eng.state.phase_tick = eng.schedule[-1].ticks - 1

    await eng.tick()

    assert eng.state.phase == P.PENALTIES
    assert eng.penalty_attempts == {Team.HOME: 0, Team.AWAY: 0}
    assert eng.ws_events[-1]["type"] == "PENALTIES_STARTED"
    assert eng.ws_events[-1]["maxSecondsPerAttempt"] == 10
    assert eng.ws_events[-1]["tickRate"] == eng.cfg.match_tick_rate


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


@pytest.mark.asyncio
async def test_penalty_attempt_expires_after_ten_seconds(make_engine):
    eng = make_engine()
    eng.dt = 1.0
    eng._start_penalties()

    for _ in range(9):
        await eng.tick()
    assert eng.penalty_attempts == {Team.HOME: 0, Team.AWAY: 0}

    await eng.tick()

    assert eng.penalty_attempts == {Team.HOME: 1, Team.AWAY: 0}
    assert eng.ws_events[-1]["type"] == "PENALTY_SHOT_RESULT"
    assert eng.ws_events[-1]["status"] == "missed"


@pytest.mark.asyncio
async def test_penalty_goal_updates_partial_score(make_engine, monkeypatch):
    import app.engine.match_engine as match_engine

    eng = make_engine()
    eng.dt = 1.0
    eng._start_penalties()
    eng.state.ball.owner_id = None
    monkeypatch.setattr(match_engine, "check_goal", lambda previous, current, field: Team.HOME)

    await eng.tick()

    assert eng.penalty_score == {Team.HOME: 1, Team.AWAY: 0}
    assert eng.penalty_attempts == {Team.HOME: 1, Team.AWAY: 0}
    assert eng.ws_events[-1]["score"] == {"home": 1, "away": 0}
    assert eng.ws_events[-1]["status"] == "scored"


@pytest.mark.asyncio
async def test_penalty_shootout_stops_after_ten_attempts(make_engine):
    class LastChoice:
        @staticmethod
        def choice(values):
            return values[-1]

        @staticmethod
        def choices(values, weights):
            return [values[0]]

    eng = make_engine()
    eng.dt = 10.0
    eng.rng = LastChoice()
    eng._start_penalties()

    for _ in range(10):
        await eng.tick()

    assert eng.penalty_attempts == {Team.HOME: 5, Team.AWAY: 5}
    assert eng.state.phase == P.FINISHED


@pytest.mark.asyncio
async def test_tied_ten_shot_shootout_selects_random_winner(make_engine):
    class AwayChoice:
        @staticmethod
        def choice(values):
            return Team.AWAY if Team.AWAY in values else values[0]

        @staticmethod
        def choices(values, weights):
            return [values[0]]

    eng = make_engine()
    eng.dt = 10.0
    eng.rng = AwayChoice()
    eng._start_penalties()

    for _ in range(10):
        await eng.tick()

    assert eng.penalty_score == {Team.HOME: 0, Team.AWAY: 0}
    assert eng.penalty_winner == Team.AWAY
    assert eng.ws_events[-2]["type"] == "PENALTIES_TIEBREAK"
    assert eng.ws_events[-1]["type"] == "PENALTIES_FINISHED"


@pytest.mark.asyncio
async def test_pending_substitution_is_stored_in_memory_and_applies_on_pause(make_engine):
    eng = make_engine()
    eng.start()
    register_home_substitute(eng)

    result = eng.request_substitution(Team.HOME, "h0", "h3")

    assert result["ok"] is True
    assert result["status"] == "scheduled"
    assert eng.pending_substitution[Team.HOME]["outPlayerId"] == "h0"
    assert eng.pending_substitution[Team.HOME]["inPlayerId"] == "h3"
    assert eng.ws_events[-1]["type"] == "SUBSTITUTION_SCHEDULED"

    eng.state.phase_tick = eng.schedule[0].ticks - 1
    await eng.tick()

    assert eng.state.phase == P.HYDRATION
    assert eng.pending_substitution[Team.HOME] is None
    assert eng.changes_used_this_pause[Team.HOME] == 1
    assert eng.ws_events[-1]["type"] == "SUBSTITUTION_APPLIED"
    assert "h3" in {player.id for player in eng.state.players}
    assert "h0" not in {player.id for player in eng.state.players}


@pytest.mark.asyncio
async def test_substitution_applies_immediately_during_pause(make_engine):
    eng = make_engine()
    eng.start()
    eng.state.phase = P.HYDRATION
    register_home_substitute(eng)

    result = eng.request_substitution(Team.HOME, "h0", "h3")

    assert result["ok"] is True
    assert result["status"] == "applied"
    assert eng.changes_used_this_pause[Team.HOME] == 1
    assert eng.ws_events[-1]["type"] == "SUBSTITUTION_APPLIED"
    assert "h3" in {player.id for player in eng.state.players}
    assert "h0" not in {player.id for player in eng.state.players}


@pytest.mark.asyncio
async def test_substitution_is_blocked_if_already_used_this_pause(make_engine):
    eng = make_engine()
    eng.start()
    eng.state.phase = P.HYDRATION
    eng.changes_used_this_pause[Team.HOME] = 1
    register_home_substitute(eng)

    result = eng.request_substitution(Team.HOME, "h0", "h3")

    assert result["ok"] is False
    assert result["message"] == "Solo se permite 1 cambio por pausa"
    assert result["error_code"] == "SUBSTITUTION_LIMIT_REACHED"
    assert eng.pending_substitution[Team.HOME] is None


def test_substitution_is_rejected_when_no_future_pause_exists(make_engine):
    eng = make_engine()
    eng.start()
    eng._segment_index = len(eng.schedule) - 1
    eng.state.phase = P.PLAY
    eng.state.period = 4
    register_home_substitute(eng)

    result = eng.request_substitution(Team.HOME, "h0", "h3")

    assert result["ok"] is False
    assert result["error_code"] == "SUBSTITUTION_NO_FUTURE_PAUSE"
    assert eng.pending_substitution[Team.HOME] is None


@pytest.mark.parametrize(
    ("out_player_id", "in_player_id", "coach_active", "phase", "error_code"),
    [
        ("invalid", "h3", False, P.PLAY, "SUBSTITUTION_INVALID_OUT_PLAYER"),
        ("h0", "invalid", False, P.PLAY, "SUBSTITUTION_INVALID_IN_PLAYER"),
        ("h0", "h3", True, P.PLAY, "SUBSTITUTION_COACH_ACTIVE"),
        ("h0", "h3", False, P.PRE, "SUBSTITUTION_INVALID_PHASE"),
    ],
)
def test_substitution_rejections_include_error_codes(
    make_engine, out_player_id, in_player_id, coach_active, phase, error_code
):
    eng = make_engine()
    eng.start()
    eng.state.phase = phase
    eng.coach_active[Team.HOME] = coach_active
    register_home_substitute(eng)

    result = eng.request_substitution(Team.HOME, out_player_id, in_player_id)

    assert result["ok"] is False
    assert result["error_code"] == error_code


def test_rejected_substitution_reports_already_pending_error_code(make_engine):
    eng = make_engine()
    eng.start()
    register_home_substitute(eng)
    eng.pending_substitution[Team.HOME] = {
        "outPlayerId": "h1",
        "inPlayerId": "h3",
    }

    result = eng.request_substitution(Team.HOME, "h0", "h3")

    assert result["ok"] is False
    assert result["error_code"] == "SUBSTITUTION_ALREADY_PENDING"


@pytest.mark.asyncio
async def test_resume_clears_changes_used_this_pause(make_engine):
    eng = make_engine()
    eng.start()
    eng.state.phase = P.HYDRATION
    eng.changes_used_this_pause[Team.HOME] = 1

    eng._enter_segment(0)

    assert eng.changes_used_this_pause[Team.HOME] == 0