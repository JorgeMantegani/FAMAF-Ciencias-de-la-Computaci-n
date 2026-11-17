"""Acreditación única de los puntos de ligas terminadas al ranking global."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.match import ESTADO_FINISHED, Match
from app.models.room import (
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_TYPE_PRIVATE,
    ROOM_TYPE_PUBLIC,
    Room,
)


def settle_league_ranking(db: Session, league_id: str) -> bool:
    """Cierra y acredita sin commit: el llamador confirma o revierte todo junto.

    El UPDATE condicional reclama el cierre una sola vez, incluso entre workers.
    Los marcadores finales son la fuente de puntos (3 victoria, 1 empate), para
    que un callback repetido no duplique los puntos acumulados en Enrollment.
    """
    matches = select(Match.id).where(Match.room_id == Room.id)
    claimed = db.execute(
        update(Room)
        .where(
            Room.id == league_id,
            Room.type.in_((ROOM_TYPE_PUBLIC, ROOM_TYPE_PRIVATE)),
            Room.status.in_((ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED)),
            Room.ranking_settled.is_(False),
            matches.exists(),
            ~matches.where(Match.status != ESTADO_FINISHED).exists(),
        )
        .values(status=ROOM_STATUS_FINISHED, ranking_settled=True)
        .returning(Room.type)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if claimed is None:
        return False

    if claimed == ROOM_TYPE_PUBLIC:
        points = {}
        for match in db.scalars(select(Match).where(Match.room_id == league_id)):
            home, away = match.home_club_id, match.away_club_id
            home_points = 3 if match.home_goals > match.away_goals else 0
            away_points = 3 if match.away_goals > match.home_goals else 0
            if match.home_goals == match.away_goals:
                home_points = away_points = 1
            points[home] = points.get(home, 0) + home_points
            points[away] = points.get(away, 0) + away_points
        # Orden estable de bloqueo y suma SQL para conservar premios concurrentes.
        for club_id, amount in sorted(points.items()):
            db.execute(
                update(Club).where(Club.id == club_id)
                .values(ranking_points=Club.ranking_points + amount)
            )
    return True


def recover_finished_league_rankings(db: Session) -> int:
    """Recupera ligas históricas sin acreditar; es seguro repetirlo al arrancar."""
    league_ids = db.scalars(
        select(Room.id).where(
            Room.status.in_((ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED)),
            Room.ranking_settled.is_(False),
            Room.type.in_((ROOM_TYPE_PUBLIC, ROOM_TYPE_PRIVATE)),
        ).order_by(Room.id)
    ).all()
    count = sum(settle_league_ranking(db, league_id) for league_id in league_ids)
    db.commit()
    return count
