from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generar_uuid

if TYPE_CHECKING:
    from app.models.match import Match

"""Modelo de jugador en partido: la alineacion real de un encuentro."""

class MatchPlayer(Base):
    """Un jugador alineado en un partido concreto: 6 por club, 12 por partido.
    """

    __tablename__ = "match_players"
    __table_args__ = (
        UniqueConstraint(
            "match_id", "player_id", name="ux_match_players_match_player"
        ),
        Index("ix_match_players_match_id_club_id", "match_id", "club_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    match_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )

    # Redundante con el club del jugador, pero necesario: el cliente pinta cada
    # equipo de su color con el `club_id` que viene en cada tick, y resolverlo
    # via jugador implicaria un join extra en cada uno de los 15 ticks por segundo.
    club_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clubs.id"), nullable=False
    )

    player_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("players.id"), nullable=False
    )

    # Comportamiento **actual**, no el inicial
    behavior_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("behaviors.id"), nullable=False
    )

    # `es_titular` del diagrama: true si esta en cancha ahora mismo.
    on_field: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Posicion de la formacion elegida en el pre-partido. La
    # posicion de cada tick NO se guarda: vive en memoria en el motor.
    initial_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    initial_y: Mapped[float | None] = mapped_column(Float, nullable=True)

    goals: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    match: Mapped["Match"] = relationship(back_populates="match_players")