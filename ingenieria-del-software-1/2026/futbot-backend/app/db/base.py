from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase
"""Clase base declarativa y helpers comunes a todos los modelos."""

class Base(DeclarativeBase):
    """Base declarativa de SQLAlchemy 2.0.
    Todos los modelos que hereden de esta clase quedan registrados en
    `Base.metadata`
    """


def generar_uuid() -> str:
    """Genera el identificador de un recurso nuevo.
    Asi, lo que esta en la base es exactamente el string que viaja en el JSON.
    """
    return str(uuid4())


def ahora_utc() -> datetime:
    """Devuelve el instante actual en UTC, con zona horaria explicita.
    """
    return datetime.now(timezone.utc)