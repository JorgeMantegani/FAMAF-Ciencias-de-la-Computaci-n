from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generar_uuid

if TYPE_CHECKING:
    from app.models.goal import Goal
    from app.models.match_player import MatchPlayer
    from app.models.room import Room
    
"""Modelo de partido: un encuentro entre dos clubes."""

# --- Estados de un partido ---
ESTADO_SCHEDULED = "scheduled"
ESTADO_PRE_MATCH = "pre_match"
ESTADO_IN_PROGRESS = "in_progress"
ESTADO_PAUSED = "paused"
ESTADO_FINISHED = "finished"
ESTADOS_PARTIDO = (
    ESTADO_SCHEDULED,
    ESTADO_PRE_MATCH,
    ESTADO_IN_PROGRESS,
    ESTADO_PAUSED,
    ESTADO_FINISHED,
)

# Duracion por defecto de cada pausa, en segundos: dos de hidratacion mas el
# entretiempo.
DURACION_PAUSA_SEGUNDOS = 15


class Match(Base):
    """Encuentro entre dos clubes.

    En una liga, al iniciarla se crean de una vez todos los partidos del
    fixture en estado `scheduled`. En un amistoso se crea un solo partido.
    """

    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{e}'" for e in ESTADOS_PARTIDO) + ")",
            name="ck_matches_estado_valido",
        ),
        CheckConstraint(
            "home_club_id <> away_club_id", name="ck_matches_clubes_distintos"
        ),
        # En una liga, dos clubes se enfrentan una sola vez.
        UniqueConstraint(
            "room_id",
            "home_club_id",
            "away_club_id",
            name="ux_matches_room_local_visitante",
        ),
        # Para mostrar el fixture agrupado por fecha.
        Index("ix_matches_room_id_round", "room_id", "round"),
        # Para encontrar los partidos en curso al reiniciar el servidor.
        Index("ix_matches_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )

    # Numero de fecha dentro del fixture. NULL en amistosos
    round: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Dos FK a la misma tabla: por eso no se declara una relationship hacia Club.
    home_club_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clubs.id"), nullable=False
    )
    away_club_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clubs.id"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(15), nullable=False, default=ESTADO_SCHEDULED
    )

    # El `result: "2-1"` del contrato se arma a partir de estos dos campos
    home_goals: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    away_goals: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # En segundos, que es la unidad del motor de simulacion. La sala guarda la
    # duracion en minutos
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    pause_duration_seconds: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=DURACION_PAUSA_SEGUNDOS
    )

    # True si el manager automatico tuvo que sortear la formacion
    auto_assigned_home: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    auto_assigned_away: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    room: Mapped["Room"] = relationship(back_populates="matches")

    match_players: Mapped[list["MatchPlayer"]] = relationship(
        back_populates="match", passive_deletes=True
    )

    goals: Mapped[list["Goal"]] = relationship(
        back_populates="match", passive_deletes=True
    )