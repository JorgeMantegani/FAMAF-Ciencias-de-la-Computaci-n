from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generar_uuid

if TYPE_CHECKING:
    from app.models.room import Room

"""Modelo de escuadra: los 6 jugadores elegidos y su comportamiento."""

# --- Roles dentro de la escuadra ---
ROLE_STARTER = "starter"
ROLE_SUBSTITUTE = "substitute"
SQUAD_ROLES = (ROLE_STARTER, ROLE_SUBSTITUTE)

# Cantidad exacta de cada rol, fijada por el alcance del proyecto.
STARTER_COUNT = 3
SUBSTITUTE_COUNT = 3

class SquadEntry(Base):
    """Un jugador convocado por un club, con el comportamiento que le asigno.
    """

    __tablename__ = "squad_entries"
    __table_args__ = (
        CheckConstraint(
            f"role IN ('{ROLE_STARTER}', '{ROLE_SUBSTITUTE}')",
            name="ck_squad_entries_role_valid",
        ),
        # El mismo jugador no puede ser convocado dos veces en la misma sala
        UniqueConstraint(
            "room_id", "player_id", name="ux_squad_entries_room_player"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )

    # Sin CASCADE a proposito: el borrado de un jugador es logico.
    player_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("players.id"), nullable=False
    )

    # Comportamiento con el que el jugador arranca cada partido.
    behavior_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("behaviors.id"), nullable=False
    )

    # si es titular  o suplente
    role: Mapped[str] = mapped_column(String(10), nullable=False)

    room: Mapped["Room"] = relationship(back_populates="squad_entries")