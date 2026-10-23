from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ahora_utc, generar_uuid

if TYPE_CHECKING:
    from app.models.club import Club
    
"""Modelo de comportamiento: el script Python de decision."""

class Behavior(Base):
    """Codigo Python que decide la jugada de un jugador en cada tick.
    """

    __tablename__ = "behaviors"
    __table_args__ = (
        # Amarra las dos formas de decir lo mismo.
        CheckConstraint(
            "is_preprogrammed = (club_id IS NULL)",
            name="ck_behaviors_preprogramado_sin_club",
        ),
        # Nombre unico dentro del club (409 BEHAVIOR_NAME_TAKEN).
        Index(
            "ux_behaviors_club_id_name_vivos",
            "club_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    # NULL = comportamiento preprogramado del sistema, visible para todos.
    club_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # Codigo Python ya validado contra la API de primitivas
    code: Mapped[str] = mapped_column(Text, nullable=False)

    is_preprogrammed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Borrado logico: los partidos ya jugados referencian el comportamiento con el que se jugaron.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    # `onupdate` lo refresca solo en cada edicion del codigo
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=ahora_utc, onupdate=ahora_utc
    )

    club: Mapped["Club | None"] = relationship(back_populates="behaviors")