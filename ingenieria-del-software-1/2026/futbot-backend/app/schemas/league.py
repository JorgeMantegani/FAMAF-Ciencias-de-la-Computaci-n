from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.squad_entry import STARTER_COUNT, SUBSTITUTE_COUNT


class SquadSelection(BaseModel):
    player_id: str
    behavior_id: str


class CreateLeague(BaseModel):
    name: str
    is_private: bool = False
    has_penalty_shootout: bool = False
    password: str | None = None
    min_clubs: int = Field(gt=0)
    max_clubs: int = Field(gt=0)
    match_duration: int = Field(gt=0)
    starters: list[SquadSelection] = Field(
        min_length=STARTER_COUNT, max_length=STARTER_COUNT
    )
    substitutes: list[SquadSelection] = Field(
        min_length=SUBSTITUTE_COUNT, max_length=SUBSTITUTE_COUNT
    )


class LeagueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    is_private: bool
    has_penalty_shootout: bool = False
    started: bool
    creator_id: str
    code_to_join: str


class ListLeagueResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    name: str
    participants_count: int
    started: bool
    is_private: bool
    has_penalty_shootout: bool


class LeagueStanding(BaseModel):
    club_id: str
    club_name: str
    points: int
    matches_played: int
    matches_won: int
    matches_drawn: int
    matches_lost: int
    goals_for: int
    goals_against: int
    goal_difference: int


class JoinLeagueSelection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    player_id: str
    behavior_id: str


class JoinLeagueRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Only checked when the league is private.
    password: str | None = None
    starters: list[JoinLeagueSelection] = Field(
        alias="titulares", min_length=STARTER_COUNT, max_length=STARTER_COUNT
    )
    substitutes: list[JoinLeagueSelection] = Field(
        alias="suplentes", min_length=SUBSTITUTE_COUNT, max_length=SUBSTITUTE_COUNT
    )


class JoinLeagueResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    enrollment_id: str
    club_id: str
    league_id: str


class LeagueSquadPlayerRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    player_id: str
    name: str
    role: str
    behavior_id: str
    behavior_name: str


class LeagueDetailRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    league_id: str
    name: str
    is_private: bool
    status: str
    min_clubs: int
    max_clubs: int
    enrolled_clubs: int
    match_duration_minutes: int
    is_enrolled: bool
    # Only the requesting club's squad; None when it is not enrolled.
    my_squad: list[LeagueSquadPlayerRead] | None


class LineupUpdateRequest(BaseModel):
    starters: list[str] = Field(min_length=3, max_length=3)
    substitutes: list[str] = Field(min_length=3, max_length=3)


class LineupUpdateResponse(BaseModel):
    message: str
    effective_next_match: bool = Field(alias="effectiveNextMatch")
    starters: list[str]
    substitutes: list[str]

    model_config = ConfigDict(populate_by_name=True)
