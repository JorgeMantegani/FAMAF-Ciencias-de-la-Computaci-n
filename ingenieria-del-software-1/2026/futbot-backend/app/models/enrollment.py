from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ahora_utc, generar_uuid

if TYPE_CHECKING:
    from app.models.room import Room

"""Modelo de inscripcion: un club dentro de una sala."""

class Enrollment(Base):
    """Participacion de un club en una sala, con su desempeno acumulado.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("room_id", "club_id", name="ux_enrollments_room_club"),
        # Cubre "mis ligas activas y el limite de 2 ligas por club. REVISAR
        Index("ix_enrollments_club_id", "club_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )

    club_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )

    # --- Tabla de posiciones ---
    points: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    matches_played: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    matches_won: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    matches_drawn: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    matches_lost: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # Criterio de desempate cuando dos clubes terminan con los mismos puntos.
    goals_for: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    goals_against: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # Define el orden en que se muestran los clubes en el lobby.
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    room: Mapped["Room"] = relationship(back_populates="enrollments")