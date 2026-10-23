from collections.abc import Callable, Generator
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.main import app
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import (
    Room,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_FRIENDLY,
)
from app.models.squad_entry import ROLE_STARTER, SquadEntry
from app.models.user import User
from app.services.friendly_service import FriendlyService
from types import SimpleNamespace

"""Tests de POST /api/friendly/rooms/{room_id}/join."""


# --- Fabricas (solo lo que la base exige por claves foraneas) ---


def crear_club(db: Session, nombre: str) -> Club:
    usuario = User(username=nombre, email=f"{nombre}@futbot.test", password_hash="hash-de-prueba")
    db.add(usuario)
    db.flush()
    club = Club(user_id=usuario.id, name=f"Club {nombre}")
    db.add(club)
    db.commit()
    return club


def crear_jugadores(db: Session, club_id: str, cantidad: int = 6) -> list[Player]:
    jugadores = [
        Player(club_id=club_id, name=f"Jugador {i}",
               power=60, agility=60, control=60, speed=60, strength=60)
        for i in range(cantidad)
    ]
    db.add_all(jugadores)
    db.commit()
    return jugadores


def crear_sala(db: Session, creator_club_id: str) -> Room:
    """Amistoso con su anfitrion inscrito, igual que lo deja create_room."""
    sala = Room(
        type=ROOM_TYPE_FRIENDLY, min_clubs=2, max_clubs=2, match_duration_minutes=10,
        status=ROOM_STATUS_WAITING_GUEST, creator_club_id=creator_club_id, code="ABC123",
    )
    db.add(sala)
    db.flush()
    db.add(Enrollment(room_id=sala.id, club_id=creator_club_id))
    db.commit()
    return sala

CODIGO = "ABC123"

def armar_body(jugadores: list[Player], comportamiento: Behavior, code: str = CODIGO) -> dict:
    seleccion = lambda j: {"playerId": j.id, "behaviorId": comportamiento.id}
    return {
        "code": code,
        "titulares": [seleccion(j) for j in jugadores[:3]],
        "suplentes": [seleccion(j) for j in jugadores[3:6]],
    }


def url(room_id: str) -> str:
    return f"/api/friendly/rooms/{room_id}/join"


# --- Fixtures de datos ---


@pytest.fixture
def anfitrion(db: Session) -> Club:
    return crear_club(db, "anfitrion")


@pytest.fixture
def invitado(db: Session) -> Club:
    return crear_club(db, "invitado")


@pytest.fixture
def sala(db: Session, anfitrion: Club) -> Room:
    return crear_sala(db, anfitrion.id)


@pytest.fixture
def jugadores(db: Session, invitado: Club) -> list[Player]:
    return crear_jugadores(db, invitado.id, 6)


@pytest.fixture
def comportamiento(db: Session) -> Behavior:
    comportamiento = Behavior(
        name="Preprogramado de prueba",
        code="def behavior(player):\n    pass",
        is_preprogrammed=True,
    )
    db.add(comportamiento)
    db.commit()
    return comportamiento


# --- Mocks ---


@pytest.fixture
def como() -> Generator[Callable[[str], None], None, None]:
    """Mock de autenticacion: como(club.id) simula a ese usuario logueado."""

    def _como(club_id: str) -> None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            club=SimpleNamespace(id=club_id)
        )

    yield _como
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def validacion(monkeypatch) -> MagicMock:
    """Mock de la validacion de jugadores y comportamientos (logica de la otra branch).

    Por defecto 'pasa'. Un test puede darle side_effect para simular un error.
    """
    mock = MagicMock()
    monkeypatch.setattr(FriendlyService, "validate_players_and_behaviors", mock)
    return mock


@pytest.fixture(autouse=True)
def broadcast(monkeypatch) -> AsyncMock:
    """Mock del aviso por WebSocket: no se abre ninguna conexion real."""
    mock = AsyncMock()
    monkeypatch.setattr("app.routers.friendly_rooms.manager.broadcast", mock)
    return mock


# --- Caso feliz ---


def test_unirse_devuelve_200_y_la_respuesta_del_contrato(
    client: TestClient, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    sala_id, invitado_id = sala.id, invitado.id
    como(invitado_id)

    r = client.post(url(sala_id), json=armar_body(jugadores, comportamiento))

    assert r.status_code == 200, r.json()
    assert r.json() == {"roomId": sala_id, "status": "readyToStart", "awayClub": invitado_id}


def test_unirse_asocia_al_visitante_y_cambia_el_estado(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    sala_id, invitado_id = sala.id, invitado.id
    como(invitado_id)

    client.post(url(sala_id), json=armar_body(jugadores, comportamiento))

    db.expire_all()
    assert db.get(Room, sala_id).status == ROOM_STATUS_READY_TO_START
    assert db.query(Enrollment).filter_by(room_id=sala_id, club_id=invitado_id).count() == 1


def test_unirse_carga_la_plantilla_del_visitante(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    sala_id, invitado_id = sala.id, invitado.id
    ids_invitado = {j.id for j in jugadores}
    como(invitado_id)

    client.post(url(sala_id), json=armar_body(jugadores, comportamiento))

    entradas = [
        e for e in db.query(SquadEntry).filter_by(room_id=sala_id)
        if e.player_id in ids_invitado
    ]
    assert len(entradas) == 6
    assert sum(e.role == ROLE_STARTER for e in entradas) == 3


# --- Sala ---


def test_sala_inexistente_devuelve_404_con_el_formato_de_error(
    client: TestClient, como, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    como(invitado.id)

    r = client.post(
        url("00000000-0000-0000-0000-000000000000"),
        json=armar_body(jugadores, comportamiento),
    )

    assert r.status_code == 404
    assert {"detail", "error_code"} <= r.json().keys()   # formato unico del contrato


def test_sala_completa_devuelve_400_y_no_se_modifica(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    sala_id = sala.id
    sala.status = ROOM_STATUS_READY_TO_START   # Ya tiene invitado
    db.commit()
    como(invitado.id)

    r = client.post(url(sala_id), json=armar_body(jugadores, comportamiento))

    assert r.status_code == 400
    assert db.query(Enrollment).filter_by(room_id=sala_id).count() == 1   # Solo el anfitrion


def test_sala_iniciada_devuelve_400(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    sala_id = sala.id
    sala.status = ROOM_STATUS_IN_PROGRESS
    db.commit()
    como(invitado.id)

    r = client.post(url(sala_id), json=armar_body(jugadores, comportamiento))

    assert r.status_code == 400

# --- Codigo de sala (contrasena) ---


def test_codigo_incorrecto_devuelve_404_y_no_une_a_la_sala(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior, validacion: MagicMock,
) -> None:
    sala_id = sala.id
    como(invitado.id)

    r = client.post(url(sala_id), json=armar_body(jugadores, comportamiento, code="ZZZZZZ"))

    assert r.status_code == 404
    db.expire_all()
    assert db.get(Room, sala_id).status == ROOM_STATUS_WAITING_GUEST   # La sala sigue abierta
    assert db.query(Enrollment).filter_by(room_id=sala_id).count() == 1
    validacion.assert_not_called()   # Ni siquiera se llega a validar jugadores


def test_codigo_en_minusculas_es_valido(
    client: TestClient, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    como(invitado.id)

    r = client.post(url(sala.id), json=armar_body(jugadores, comportamiento, code=" abc123 "))

    assert r.status_code == 200   # Se normaliza: sin espacios y en mayusculas


def test_payload_sin_codigo_devuelve_error_de_validacion(
    client: TestClient, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    como(invitado.id)
    body = armar_body(jugadores, comportamiento)
    del body["code"]

    r = client.post(url(sala.id), json=body)

    assert r.status_code == 422


def test_codigo_incorrecto_no_revela_si_la_sala_esta_completa(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    sala_id = sala.id
    sala.status = ROOM_STATUS_READY_TO_START   # Sala completa
    db.commit()
    como(invitado.id)

    r = client.post(url(sala_id), json=armar_body(jugadores, comportamiento, code="ZZZZZZ"))

    assert r.status_code == 404   # No 400: sin el codigo correcto no se sabe nada de la sala

# --- Jugadores ---


def test_club_con_menos_de_6_jugadores_devuelve_400(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    comportamiento: Behavior, validacion: MagicMock,
) -> None:
    pocos = crear_jugadores(db, invitado.id, 5)   # El club solo tiene 5 (este test no usa el fixture jugadores)
    como(invitado.id)

    r = client.post(url(sala.id), json=armar_body(pocos + pocos[:1], comportamiento))

    assert r.status_code == 400
    validacion.assert_not_called()   # El chequeo de cantidad va antes que la validacion


def test_valida_la_seleccion_con_el_club_autenticado(
    client: TestClient, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior, validacion: MagicMock,
) -> None:
    invitado_id = invitado.id
    como(invitado_id)

    client.post(url(sala.id), json=armar_body(jugadores, comportamiento))

    validacion.assert_called_once_with(invitado_id, ANY)   # Se valida contra SU club, no otro


def test_error_de_validacion_se_propaga_y_no_une_a_la_sala(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior, validacion: MagicMock,
) -> None:
    sala_id = sala.id
    validacion.side_effect = HTTPException(400, detail="Jugador invalido.")
    como(invitado.id)

    r = client.post(url(sala_id), json=armar_body(jugadores, comportamiento))

    assert r.status_code == 400
    db.expire_all()
    assert db.get(Room, sala_id).status == ROOM_STATUS_WAITING_GUEST   # La sala sigue abierta
    assert db.query(Enrollment).filter_by(room_id=sala_id).count() == 1


def test_payload_sin_suplentes_devuelve_error_de_validacion(
    client: TestClient, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior,
) -> None:
    como(invitado.id)
    body = armar_body(jugadores, comportamiento)
    del body["suplentes"]

    r = client.post(url(sala.id), json=body)

    assert r.status_code == 422   # AJUSTAR si tu handler de errores convierte los 422 a otro codigo


# --- Aviso por WebSocket (mockeado) ---


def test_unirse_avisa_a_la_sala_por_websocket(
    client: TestClient, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior, broadcast: AsyncMock,
) -> None:
    sala_id, invitado_id = sala.id, invitado.id
    como(invitado_id)

    client.post(url(sala_id), json=armar_body(jugadores, comportamiento))

    broadcast.assert_awaited_once_with(
        sala_id,
        {"type": "guest_joined", "awayClub": invitado_id, "status": "readyToStart"},
    )


def test_si_falla_unirse_no_se_avisa_por_websocket(
    client: TestClient, db: Session, como, sala: Room, invitado: Club,
    jugadores: list[Player], comportamiento: Behavior, broadcast: AsyncMock,
) -> None:
    sala.status = ROOM_STATUS_IN_PROGRESS
    db.commit()
    como(invitado.id)

    client.post(url(sala.id), json=armar_body(jugadores, comportamiento))

    broadcast.assert_not_awaited()


# --- Autenticacion ---


def test_sin_token_devuelve_401(
    client: TestClient, sala: Room, jugadores: list[Player], comportamiento: Behavior,
) -> None:
    r = client.post(url(sala.id), json=armar_body(jugadores, comportamiento))   # Sin override

    assert r.status_code == 401   # AJUSTAR si get_current_user devuelve otro codigo