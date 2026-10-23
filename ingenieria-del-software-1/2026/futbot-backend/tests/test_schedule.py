import pytest
from app.engine.schedule import build_schedule
from app.engine.state import MatchPhase as P


def test_default_demo_300s_15tps():
    sched = build_schedule(300, 15)
    plays = [s.ticks for s in sched if s.phase == P.PLAY]
    assert plays == [1125] * 4
    assert sum(plays) == 4500


def test_phase_sequence():
    phases = [s.phase for s in build_schedule(8, 10)]
    assert phases == [P.PLAY, P.HYDRATION, P.PLAY, P.HALFTIME,
                      P.PLAY, P.HYDRATION, P.PLAY]


def test_periods_numbered_1_to_4():
    periods = [s.period for s in build_schedule(8, 10) if s.phase == P.PLAY]
    assert periods == [1, 2, 3, 4]


def test_pauses_use_given_durations():
    sched = build_schedule(8, 10, hydration_seconds=2, halftime_seconds=3)
    assert sched[1].ticks == 20   # hidratación
    assert sched[3].ticks == 30   # entretiempo


@pytest.mark.parametrize("secs,rate", [(0, 15), (-1, 15), (300, 0)])
def test_invalid_input(secs, rate):
    with pytest.raises(ValueError):
        build_schedule(secs, rate)