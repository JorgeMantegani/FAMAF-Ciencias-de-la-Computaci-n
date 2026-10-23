from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

"""Engine, fabrica de sesiones y dependencia de base de datos."""

settings = get_settings()


def _crear_engine(database_url: str) -> Engine:
    """Construye el engine aplicando los ajustes que SQLite necesita.
    """
    connect_args: dict[str, object] = {}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(database_url, connect_args=connect_args)


engine = _crear_engine(settings.database_url)


@event.listens_for(Engine, "connect")
def _activar_foreign_keys(dbapi_connection, connection_record) -> None:
    """Activa la verificacion de claves foraneas en cada conexion SQLite.
    """
    import sqlite3

    #PRAGMA: solo se emite sobre SQLite.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesion y la cierra siempre.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()