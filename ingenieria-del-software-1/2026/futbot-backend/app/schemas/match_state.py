"""Estado publico y datos que publica el motor al completar un tick."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, NonNegativeInt, model_validator

TickPhase = Literal["PLAYING", "HYDRATION", "HALFTIME", "PENALTIES", "FINISHED"]
PAUSE_PHASES = ("HYDRATION", "HALFTIME")
PHASE_STATUS = {
    "PLAYING": "in_progress",
    "HYDRATION": "paused",
    "HALFTIME": "paused",
    "PENALTIES": "paused",
    "FINISHED": "finished",
}


class StateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Position(StateModel):
    x: float
    y: float


class BallState(Position):
    vx: float = 0
    vy: float = 0
    owner_player_id: UUID | None = None


class Score(StateModel):
    home: int = Field(ge=0, le=32767)
    away: int = Field(ge=0, le=32767)


class PenaltySnapshot(StateModel):
    shooter_id: UUID | None = None
    goalkeeper_id: UUID | None = None
    score: Score
    attempts: Score
    seconds_remaining: float = Field(ge=0)
    winner_club_id: UUID | None = None


class PlayerTick(StateModel):
    player_id: UUID
    position: Position | None = None
    on_field: bool

    @model_validator(mode="after")
    def require_position_on_field(self):
        if self.on_field and self.position is None:
            raise ValueError("Un jugador en cancha requiere posicion")
        return self


class MatchAction(StateModel):
    type: Literal["movement", "pass", "shot", "goal", "substitution", "behavior_changed", "pause", "resume"]
    player_id: UUID | None = None
    club_id: UUID | None = None
    destination: Position | None = None


class MatchTick(StateModel):
    status: Literal["in_progress", "paused", "finished"]
    phase: TickPhase
    penalty: PenaltySnapshot | None = None
    pause_duration: NonNegativeInt | None  # total seconds of the current pause
    pause_remaining: NonNegativeFloat | None  # seconds left in the pause at this snapshot
    current_time: float = Field(ge=0)
    score: Score
    ball: BallState
    players: list[PlayerTick] = Field(max_length=12)
    actions: list[MatchAction] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def require_consistent_phase(self):
        if PHASE_STATUS[self.phase] != self.status:
            raise ValueError("La fase no coincide con el estado del partido")
        in_pause = self.phase in PAUSE_PHASES
        for value in (self.pause_duration, self.pause_remaining):
            if (value is not None) != in_pause:
                raise ValueError("Solo una hidratacion o un entretiempo llevan datos de pausa")
        return self


class ClubState(StateModel):
    club_id: UUID
    name: str


class PlayerState(PlayerTick):
    club_id: UUID
    name: str
    behavior_id: UUID
    has_ball: bool


class MatchState(StateModel):
    match_id: UUID
    revision: int = Field(ge=1)
    home_club: ClubState
    away_club: ClubState
    status: Literal["in_progress", "paused", "finished"]
    phase: TickPhase
    penalty: PenaltySnapshot | None = None
    pause_duration: NonNegativeInt | None
    pause_remaining: NonNegativeFloat | None
    score: Score
    result: str
    current_time: float
    remaining_time: float
    duration_seconds: int
    ball: BallState
    players: list[PlayerState]
    actions: list[MatchAction]
