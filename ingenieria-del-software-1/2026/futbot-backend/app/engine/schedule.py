from dataclasses import dataclass
from app.engine.state import MatchPhase


@dataclass(frozen=True, slots=True)
class Segment:
    phase: MatchPhase
    ticks: int
    period: int   # 1 a 4 (las pausas llevan el periodo que acaba de terminar)


def build_schedule(
    play_seconds: float,
    tick_rate: int,
    hydration_seconds: float = 10,
    halftime_seconds: float = 15,
) -> list[Segment]:
    if play_seconds <= 0 or tick_rate <= 0:
        raise ValueError("play_seconds y tick_rate deben ser > 0")

    p = round(play_seconds * tick_rate) // 4
    if p < 1:
        raise ValueError("Duración demasiado corta para 4 periodos")
    h = round(hydration_seconds * tick_rate)
    t = round(halftime_seconds * tick_rate)

    P, H, T = MatchPhase.PLAY, MatchPhase.HYDRATION, MatchPhase.HALFTIME
    return [
        Segment(P, p, 1), Segment(H, h, 1),
        Segment(P, p, 2), Segment(T, t, 2),
        Segment(P, p, 3), Segment(H, h, 3),
        Segment(P, p, 4),
    ]