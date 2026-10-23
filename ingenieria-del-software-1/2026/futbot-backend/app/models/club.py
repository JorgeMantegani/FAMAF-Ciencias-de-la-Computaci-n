

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ahora_utc, generar_uuid

if TYPE_CHECKING:
    from app.models.behavior import Behavior
    from app.models.player import Player
    from app.models.user import User
    
"""Modelo de club: la identidad de juego del usuario."""

class Club(Base):
    """Identidad de juego: es el dueno de jugadores, comportamientos y salas.
    """

    __tablename__ = "clubs"
    __table_args__ = (
        # Red de seguridad: el ranking nunca puede quedar negativo
        CheckConstraint("ranking_points >= 0", name="ck_clubs_ranking_points_no_negativo"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    # UNIQUE ademas de FK: fuerza la relacion 1 a 1 con el usuario a nivel de base.
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # El contrato expone este campo como `club_name`
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Solo suman las ligas publicas
    ranking_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    user: Mapped["User"] = relationship(back_populates="club")

    players: Mapped[list["Player"]] = relationship(
        back_populates="club", passive_deletes=True
    )

    behaviors: Mapped[list["Behavior"]] = relationship(
        back_populates="club", passive_deletes=True
    )