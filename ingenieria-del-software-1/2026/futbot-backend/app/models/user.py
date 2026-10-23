from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ahora_utc, generar_uuid

if TYPE_CHECKING:
    from app.models.club import Club

"""Modelo de usuario: la cuenta de acceso al sistema."""

class User(Base):
    """Cuenta de acceso.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    # La unicidad de la cuenta esta aca.
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    club: Mapped["Club"] = relationship(
        back_populates="user",
        # La base ya borra el club en cascada gracias a la FK.
        passive_deletes=True,
    )