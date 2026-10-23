from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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
    from app.models.enrollment import Enrollment
    from app.models.match import Match
    from app.models.squad_entry import SquadEntry
    
"""Modelo de sala: LEAGUE publica, LEAGUE privada o amistoso."""

# --- Tipos de sala ---
ROOM_TYPE_PUBLIC = "public"
ROOM_TYPE_PRIVATE = "private"
ROOM_TYPE_FRIENDLY = "friendly"
ROOM_TYPES = (ROOM_TYPE_PUBLIC, ROOM_TYPE_PRIVATE, ROOM_TYPE_FRIENDLY)

# --- Estados de sala ---
ROOM_STATUS_WAITING_GUEST = "waiting_guest"
ROOM_STATUS_READY_TO_START = "ready_to_start"
ROOM_STATUS_IN_PROGRESS = "in_progress"
ROOM_STATUS_FINISHED = "finished"
ROOM_STATUS_CANCELLED = "cancelled"
ROOM_STATUSES = (
    ROOM_STATUS_WAITING_GUEST,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_CANCELLED,
)

# Limites de participantes de una liga.
MIN_LEAGUE_CLUBS = 3
MAX_LEAGUE_CLUBS = 30


def _list_sql(valores: tuple[str, ...]) -> str:
    """Arma la lista de un `IN (...)` de SQL a partir de constantes de Python.
    """
    return ", ".join(f"'{valor}'" for valor in valores)


class Room(Base):
    """Sala de juego: una liga o un amistoso.
    """

    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint(
            f"type IN ({_list_sql(ROOM_TYPES)})", name="ck_rooms_type_valid"
        ),
        CheckConstraint(
            f"status IN ({_list_sql(ROOM_STATUSES)})", name="ck_rooms_status_valid"
        ),
        CheckConstraint("min_clubs <= max_clubs", name="ck_rooms_club_limits_valid"),
        CheckConstraint(
            f"(type = '{ROOM_TYPE_FRIENDLY}' AND min_clubs = 2 AND max_clubs = 2)"
            f" OR (name IS NOT NULL AND min_clubs >= {MIN_LEAGUE_CLUBS}"
            f" AND max_clubs <= {MAX_LEAGUE_CLUBS})",
            name="ck_rooms_club_limits_by_type",
        ),
        # Hay contrasena si y solo si la liga es privada.
        CheckConstraint(
            f"(type = '{ROOM_TYPE_PRIVATE}') = (password_hash IS NOT NULL)",
            name="ck_rooms_private_password_required",
        ),
        # Nombre de liga unico.
        Index(
            "ux_rooms_league_name",
            "name",
            unique=True,
            sqlite_where=text(f"type IN ('{ROOM_TYPE_PUBLIC}', '{ROOM_TYPE_PRIVATE}')"),
            postgresql_where=text(f"type IN ('{ROOM_TYPE_PUBLIC}', '{ROOM_TYPE_PRIVATE}')"),
        ),
        # Cubre los dos listados: ligas publicas abiertas y amistosos esperando rival. REVISAR ESTO!!!!!!!!!!!!!!!!!
        Index("ix_rooms_type_status", "type", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    type: Mapped[str] = mapped_column(String(10), nullable=False)

    # Obligatorio en ligas, NULL en amistosos (lo fuerza el CHECK de limites).
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Solo en ligas privadas. Se guarda hasheada. REVISAR ESTO!!!!!!!!!!!!!!!!!
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # El contrato lo expone como `code_to_join` en ligas privadas y como
    # `room_code` en amistosos. Es el mismo dato, asi que la columna es una sola
    # y cada esquema Pydantic le da el nombre que ese endpoint declara.
    code: Mapped[str | None] = mapped_column(String(10), nullable=True, unique=True)

    creator_club_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clubs.id"), nullable=False
    )

    min_clubs: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_clubs: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # En minutos.
    match_duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    status: Mapped[str] = mapped_column(
        String(15), nullable=False, default=ROOM_STATUS_WAITING_GUEST
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=ahora_utc
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="room", passive_deletes=True
    )

    matches: Mapped[list["Match"]] = relationship(
        back_populates="room", passive_deletes=True
    )

    squad_entries: Mapped[list["SquadEntry"]] = relationship(
        back_populates="room", passive_deletes=True
    )
