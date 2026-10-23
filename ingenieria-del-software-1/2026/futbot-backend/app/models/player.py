from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ahora_utc, generar_uuid

if TYPE_CHECKING:
    from app.models.club import Club
    
"""Modelo de jugador: el futbolista del plantel de un club."""

# Los cinco atributos PACSS.
ATRIBUTOS_PACSS = ("power", "agility", "control", "speed", "strength")

# Rango permitido por atributo y total exacto a repartir entre los cinco.
PACSS_MINIMO = 20
PACSS_MAXIMO = 100
PACSS_SUMA_EXACTA = 300


class Player(Base):
    """Futbolista del plantel.
    """

    __tablename__ = "players"
    __table_args__ = (
        *(
            CheckConstraint(
                f"{atributo} BETWEEN {PACSS_MINIMO} AND {PACSS_MAXIMO}",
                name=f"ck_players_{atributo}_rango",
            )
            for atributo in ATRIBUTOS_PACSS
        ),
        CheckConstraint(
            " + ".join(ATRIBUTOS_PACSS) + f" = {PACSS_SUMA_EXACTA}",
            name="ck_players_suma_pacss",
        ),
        Index(
            "ix_players_club_id_vivos",
            "club_id",
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    club_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # --- Atributos PACSS ---
    power: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # fuerza de pateo
    agility: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # espera entre pateos
    control: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # distancia de control
    speed: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # velocidad y aceleracion
    strength: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # imposicion en choques

    # True mientras el jugador esta en un partido en curso.
    is_playing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Borrado logico. Los listados filtran `deleted_at IS NULL`.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    club: Mapped["Club"] = relationship(back_populates="players")