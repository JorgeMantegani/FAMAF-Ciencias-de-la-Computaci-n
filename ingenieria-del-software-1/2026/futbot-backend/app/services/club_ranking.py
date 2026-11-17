"""Ranking global: posiciones calculadas antes de aplicar la paginación."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.club import Club
from app.schemas.club_ranking import ClubRankingResponse, RankingItem, UserClubRanking


def get_club_ranking(
    db: Session, club_id: str, page: int = 1, size: int = 20
) -> ClubRankingResponse:
    """El club solicitante debe existir (lo garantiza get_current_club)."""
    if page < 1 or size < 1:
        raise ValueError("page y size deben ser positivos")

    ranked = select(
        Club.id.label("club_id"),
        Club.name.label("club_name"),
        Club.avatar_url.label("avatar"),
        Club.ranking_points,
        func.row_number()
        .over(order_by=(Club.ranking_points.desc(), Club.name.asc(), Club.id.asc()))
        .label("position"),
        func.count().over().label("total_clubs"),
    ).subquery()

    # El filtro por usuario se aplica DESPUÉS de numerar todos los clubes.
    own = db.execute(select(ranked).where(ranked.c.club_id == club_id)).mappings().one()
    total = own["total_clubs"]
    total_pages = (total + size - 1) // size
    items = []
    if page <= total_pages:
        rows = db.execute(
            select(ranked)
            .order_by(ranked.c.position)
            .offset((page - 1) * size)
            .limit(min(size, total))
        ).mappings()
        items = [RankingItem.model_validate(row) for row in rows]

    return ClubRankingResponse(
        items=items,
        page=page,
        size=size,
        total_pages=total_pages,
        total_clubs=total,
        user_club_ranking=UserClubRanking(
            position=own["position"],
            ranking_points=own["ranking_points"],
        ),
    )
