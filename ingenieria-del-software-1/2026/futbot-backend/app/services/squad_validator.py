"""Validación de plantillas compartida por los flujos que eligen jugadores y comportamientos."""

from collections.abc import Sequence
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.player import Player
from app.models.squad_entry import STARTER_COUNT, SUBSTITUTE_COUNT


class Selection(Protocol):
    player_id: str
    behavior_id: str


def _invalid_squad(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"detail": message, "error_code": "INVALID_SQUAD"},
    )


def validate_squad_selection(
    db: Session,
    club_id: str,
    starters: Sequence[Selection],
    substitutes: Sequence[Selection],
) -> None:
    """Valida cantidades, repetidos y que jugadores y comportamientos sean usables por el club."""
    if len(starters) != STARTER_COUNT or len(substitutes) != SUBSTITUTE_COUNT:
        raise _invalid_squad(
            f"Se requieren exactamente {STARTER_COUNT} titulares y {SUBSTITUTE_COUNT} suplentes."
        )

    selections = [*starters, *substitutes]
    player_ids = {s.player_id for s in selections}
    if len(player_ids) != len(selections):
        raise _invalid_squad("No se puede seleccionar el mismo jugador más de una vez.")

    own_players = db.scalar(
        select(func.count())
        .select_from(Player)
        .where(
            Player.id.in_(player_ids),
            Player.club_id == club_id,
            Player.deleted_at.is_(None),
        )
    )
    # Inexistente y ajeno comparten error, así no se revelan jugadores de otros clubes.
    if own_players != len(player_ids):
        raise _invalid_squad("Algún jugador elegido no existe, no es de tu club o fue eliminado.")

    behavior_ids = {s.behavior_id for s in selections}
    usable_behaviors = db.scalar(
        select(func.count())
        .select_from(Behavior)
        .where(
            Behavior.id.in_(behavior_ids),
            Behavior.deleted_at.is_(None),
            # club_id IS NULL indica un comportamiento preprogramado.
            or_(Behavior.club_id == club_id, Behavior.club_id.is_(None)),
        )
    )
    if usable_behaviors != len(behavior_ids):
        raise _invalid_squad(
            "Algún comportamiento elegido no existe, no es de tu club o fue eliminado."
        )
