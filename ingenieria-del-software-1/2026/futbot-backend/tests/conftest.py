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
from app.models.match import Match, ESTADO_PRE_MATCH
from app.models.match_player import MatchPlayer
from app.models.room import ( Room, ROOM_TYPE_FRIENDLY, ROOM_STATUS_READY_TO_START,
)


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
        email_verified_at=datetime.now(timezone.utc),
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
        code="""
def behavior(player):
    pelota = player.encontrar_pelota()
    player.correr(pelota)
""",
        is_preprogrammed=True,
    )
    db.add(behavior)
    db.commit()
    return behavior


@pytest.fixture
def login_user(db: Session) -> User:
    user = User(
        email_verified_at=datetime.now(timezone.utc),
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


@pytest.fixture
def club_players(crear_player, club) -> list[Player]:
    """Crea 6 jugadores del club del usuario de prueba usando la fábrica crear_player."""
    return [crear_player(club.id, name=f"Player {i + 1}") for i in range(6)]


@pytest.fixture
def other_club(db: Session) -> Club:
    """Segundo club, con su propio usuario, para probar el aislamiento entre clubes."""
    other_user = User(username="other", email="other@other.com", password_hash="hash")
    other_user.club = Club(name="Other Club")
    db.add(other_user)
    db.commit()
    return other_user.club

@pytest.fixture
def other_club_players(crear_player, other_club) -> list[Player]:
    """Crea 6 jugadores del otro club usando la fábrica crear_player."""
    return [crear_player(other_club.id, name=f"Other Player {i + 1}") for i in range(6)]

@pytest.fixture
def add_default_behaviors(db: Session):
    """Agrega comportamientos preprogramados por defecto a la base de datos de prueba."""
    behaviors = [
        Behavior(
            name="defense",
            code="""
                def behavior(player):
                    # Comportamiento de defensa genérico
                    player.correr((0, 0))  # Ir a una posición defensiva
            """,
            is_preprogrammed=True,
        ),
        Behavior(
            name="goalkeeper",
            code="""
                def behavior(player):
                    # Comportamiento de portero genérico
                    player.quedarse_en_porteria()  # Mantenerse en la portería
            """,
            is_preprogrammed=True,
        ),
    ]
    db.add_all(behaviors)
    db.commit()

@pytest.fixture(autouse=True)
def email_sender():
    from app.services.email_sender import get_email_sender

    class FakeEmailSender:
        def __init__(self):
            self.messages = []
            self.password_reset_messages = []
            self.fail = False

        def send_verification(self, email, url):
            if self.fail:
                raise RuntimeError("SMTP unavailable")
            self.messages.append((email, url))

        def send_password_reset(self, email, url):
            if self.fail:
                raise RuntimeError("SMTP unavailable")
            self.password_reset_messages.append((email, url))

    sender = FakeEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    yield sender
    app.dependency_overrides.pop(get_email_sender, None)

@pytest.fixture
def behavior_personalizado(db: Session, club: Club) -> Behavior:
    """Crea un comportamiento custom del usuario (no preprogramado)."""
    behavior = Behavior(
        club_id=club.id,
        name="Mi script loco",
        code="""
def behavior(player):
   pelota = player.encontrar_pelota()
   player.correr(pelota)
""",
        is_preprogrammed=False,
    )
    db.add(behavior)
    db.commit()
    return behavior


@pytest.fixture
def match_en_pre_match(
    db: Session, 
    club: Club, 
    other_club: Club, 
    club_players, 
    other_club_players, 
    behavior_personalizado,
    comportamiento_prueba # Usamos el preprogramado para rellenar
) -> Match:
    room = Room(
        type=ROOM_TYPE_FRIENDLY,
        creator_club_id=club.id,
        min_clubs=2,
        max_clubs=2,
        match_duration_minutes=5,
        status=ROOM_STATUS_READY_TO_START,
    )
    db.add(room)
    db.commit()

    """Crea un partido válido 3v3 en estado PRE_MATCH."""
    match = Match(
        room_id=room.id,
        home_club_id=club.id,
        away_club_id=other_club.id,
        status=ESTADO_PRE_MATCH,
        duration_seconds=300,
        pause_duration_seconds=10
    )
    db.add(match)
    db.commit()

    for i in range(3):
        b_id = behavior_personalizado.id if i == 0 else comportamiento_prueba.id
        db.add(MatchPlayer(
            match_id=match.id,
            club_id=club.id,
            player_id=club_players[i].id,
            behavior_id=b_id,
            on_field=True
        ))
    
    for i in range(3):
        db.add(MatchPlayer(
            match_id=match.id,
            club_id=other_club.id,
            player_id=other_club_players[i].id,
            behavior_id=comportamiento_prueba.id,
            on_field=True
        ))
        
    db.commit()
    return match