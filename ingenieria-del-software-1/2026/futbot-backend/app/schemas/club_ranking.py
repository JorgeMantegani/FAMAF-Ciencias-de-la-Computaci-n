"""Contrato del ranking global de clubes."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class RankingItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    position: int
    club_id: str
    club_name: str
    avatar: str | None
    ranking_points: int


class UserClubRanking(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    position: int
    ranking_points: int


class ClubRankingResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[RankingItem]
    page: int
    size: int
    total_pages: int
    total_clubs: int
    user_club_ranking: UserClubRanking
