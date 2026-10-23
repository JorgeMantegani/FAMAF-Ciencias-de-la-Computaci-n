"""Configuracion y fixtures de las pruebas del backend."""
import os
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from time import time
import uuid

# Definir antes de importar la aplicacion para no usar la clave real.
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-not-for-production"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 - registra las tablas en Base.metadata
from app.core.config import get_settings
from app.core.security import create_access_token, password_context
from app.db.base import Base
from app.db.session import _crear_engine, get_db
from app.main import app
from app.models.auth_session import AuthSession
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.player import Player
from app.models.user import User


@pytest.fixture
def engine(tmp_path) -> Generator[Engine, None, None]:
    """Engine contra una base SQLite temporal, propia de cada test."""
    engine = _crear_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """Sesion de base de datos apuntando a la base temporal del test."""
    fabrica = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sesion = fabrica()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP con la dependencia de base de datos redirigida al test."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --- Helpers de creacion de datos ---

@pytest.fixture
def user(db: Session) -> User:
    usuario = User(
        username="tester",
        email="tester@futbot.test",
        password_hash="hash-de-prueba",
    )
    usuario.club = Club(name="Club de Prueba")
    db.add(usuario)
    db.commit()
    return usuario


@pytest.fixture
def club(user: User) -> Club:
    return user.club


@pytest.fixture
def auth_headers(db: Session, club: Club) -> dict[str, str]:
    """
    Crea una AuthSession activa para el usuario del club fixture
    y retorna los headers HTTP con el Bearer token listo para usar.
    """
    user = club.user

    expires_at = int(time()) + 3600
    session_id = str(uuid.uuid4())

    session = AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_hash="dummy_refresh_hash_for_tests",
        expires_at=expires_at,
        revoked=False,
    )
    db.add(session)
    db.commit()

    token = create_access_token(
        user_id=user.id,
        session_id=session.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def comportamiento_prueba(db: Session) -> Behavior:
    """
    Crea un comportamiento preprogramado generico para los tests.
    """
    behavior = Behavior(
        name="Ataque Directo",
        code="ATAQUE_DIRECTO",
        is_preprogrammed=True,
    )
    db.add(behavior)
    db.commit()
    return behavior


@pytest.fixture
def login_user(db: Session) -> User:
    user = User(
        username="login-tester",
        email="login@futbot.test",
        password_hash=password_context.hash("correct-password"),
    )
    user.club = Club(name="Login Club")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def crear_player(db: Session):
    """Fabrica de jugadores usando la base aislada de cada prueba."""

    def crear(club_id: str, **overrides) -> Player:
        atributos = {
            "name": "JugadorDePrueba",
            "power": 60,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        }
        atributos.update(overrides)

        player = Player(club_id=club_id, **atributos)
        db.add(player)
        db.commit()
        db.refresh(player)
        return player

    return crear


@pytest.fixture
def enable_optional_refresh(monkeypatch):
    monkeypatch.setattr(get_settings(), "refresh_enabled", True)


@pytest.fixture
def fixed_session_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "refresh_enabled", False)
    monkeypatch.setattr(settings, "jwt_expire_minutes", 5)


@pytest.fixture(autouse=True)
def isolated_live_state():
    from app.engine.live_state import match_states
    match_states.clear()
    yield
    match_states.clear()
