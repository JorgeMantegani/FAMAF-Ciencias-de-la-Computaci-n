from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generar_uuid

if TYPE_CHECKING:
    from app.models.match import Match

"""Modelo de gol: el historial de goles de un partido (evento GOAL_SCORED)."""

class Goal(Base):
    """Un gol convertido, con su autor y el momento en que ocurrio.
    """

    __tablename__ = "goals"
    __table_args__ = (
        # Los goles siempre se piden por partido y en orden cronologico.
        Index("ix_goals_match_id_second", "match_id", "second"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    match_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )

    # El club que sumo el gol, que en un gol en contra no es el club del autor.
    club_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clubs.id"), nullable=False
    )

    # NULL cuando es gol en contra o no hay un autor claro.
    player_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("players.id"), nullable=True
    )

    # Segundo del partido en que se convirtio.
    second: Mapped[int] = mapped_column(Integer, nullable=False)

    match: Mapped["Match"] = relationship(back_populates="goals")