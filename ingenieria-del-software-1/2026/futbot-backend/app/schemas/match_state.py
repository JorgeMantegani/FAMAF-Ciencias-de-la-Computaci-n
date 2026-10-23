"""Estado publico y datos que publica el motor al completar un tick."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    current_time: float = Field(ge=0)
    score: Score
    ball: BallState
    players: list[PlayerTick] = Field(max_length=12)
    actions: list[MatchAction] = Field(default_factory=list, max_length=256)


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
    score: Score
    result: str
    current_time: float
    remaining_time: float
    duration_seconds: int
    ball: BallState
    players: list[PlayerState]
    actions: list[MatchAction]
