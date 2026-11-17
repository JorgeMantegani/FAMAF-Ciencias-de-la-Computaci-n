import ast
import logging
from pathlib import Path

from sqlalchemy import Engine, func, inspect, select, text
from sqlalchemy.orm import Session

# Importar `app.models` registra las tablas en `Base.metadata`. Sin este
# import, `create_all()` no tendria nada que crear.
from app.models.behavior import Behavior

"""Creacion del schema y carga de los comportamientos preprogramados."""

import app.models  # noqa: F401
from app.db.base import Base

logger = logging.getLogger(__name__)

# Directorio donde viven los comportamientos por defecto del sistema.
DIRECTORIO_DEFAULTS = Path(__file__).resolve().parent.parent / "behaviors" / "defaults"

def crear_tablas(engine: Engine) -> None:
    """Aplica la migración de correo y crea las tablas que todavía no existen."""
    from app.db.migrations import migrate_email_verification

    migrate_email_verification(engine)
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    room_columns = {column["name"] for column in inspector.get_columns("rooms")}
    match_columns = {column["name"] for column in inspector.get_columns("matches")}
    with engine.begin() as connection:
        if "ranking_settled" not in room_columns:
            connection.execute(text(
                "ALTER TABLE rooms ADD COLUMN ranking_settled BOOLEAN NOT NULL DEFAULT FALSE"
            ))
        if "has_penalty_shootout" not in room_columns:
            connection.execute(text(
                "ALTER TABLE rooms ADD COLUMN has_penalty_shootout "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            ))
        if "penalty_winner_club_id" not in match_columns:
            connection.execute(text(
                "ALTER TABLE matches ADD COLUMN penalty_winner_club_id "
                "VARCHAR(36) REFERENCES clubs(id)"
            ))



def _leer_comportamiento(archivo: Path) -> tuple[str, str]:
    """Extrae el nombre y el codigo de un archivo de comportamiento default."""
    codigo = archivo.read_text(encoding="utf-8")
    if not codigo.strip():
        raise ValueError(f"El comportamiento {archivo.name} tiene codigo vacio")
    ast.parse(codigo)
    return archivo.stem, codigo


def cargar_comportamientos_por_defecto(db: Session) -> int:
    """Inserta o actualiza los comportamientos preprogramados del sistema.
    Devuelve cuantos comportamientos quedaron cargados.
    """
    archivos = sorted(DIRECTORIO_DEFAULTS.glob("*.py"))

    for archivo in archivos:
        if archivo.name == "__init__.py":
            continue

        nombre, codigo = _leer_comportamiento(archivo)

        existente = db.scalars(
            select(Behavior).where(
                Behavior.club_id.is_(None), Behavior.name == nombre
            )
        ).one_or_none()

        if existente is None:
            db.add(
                Behavior(
                    club_id=None,
                    name=nombre,
                    code=codigo,
                    is_preprogrammed=True,
                )
            )
            logger.info("Comportamiento por defecto cargado: %s", nombre)
        elif existente.code != codigo:
            # El archivo cambio desde el ultimo arranque: se actualiza la fila
            # en lugar de crear una segunda con el mismo nombre. Asi editar un
            # default en el repositorio se refleja al reiniciar.
            existente.code = codigo
            logger.info("Comportamiento por defecto actualizado: %s", nombre)

    db.commit()
    # Se cuenta en la base y no con `len(archivos)`: lo que importa reportar es
    # cuantas filas quedaron realmente, que es lo que el test de idempotencia
    # verifica que no crezca entre arranques.
    return db.scalar(
        select(func.count()).select_from(Behavior).where(Behavior.club_id.is_(None))
    )
