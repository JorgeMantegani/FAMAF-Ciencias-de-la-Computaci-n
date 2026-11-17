from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import ANY

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club
from app.main import app
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import (
    Room,
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_FRIENDLY,
    ROOM_TYPE_PUBLIC,
)
from app.models.user import User
from app.schemas.friendly_room import CreateFriendlyRoomRequest, PlayerSelection
from app.services.friendly_service import FriendlyService
from app.models.squad_entry import SquadEntry

"""Tests de GET /api/friendly/rooms/public y de la creación de salas sin código."""

URL = "/api/friendly/rooms/public"


# --- Ayudas ---


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


def crear_sala(
    db: Session, creador: Club, *, status: str = ROOM_STATUS_WAITING_GUEST,
    created_at: datetime | None = None, code: str | None = None, invitado: Club | None = None,
) -> Room:
    extra = {"created_at": created_at} if created_at else {}
    sala = Room(
        type=ROOM_TYPE_FRIENDLY, min_clubs=2, max_clubs=2, match_duration_minutes=10,
        status=status, creator_club_id=creador.id, code=code, **extra,
    )
    db.add(sala)
    db.flush()
    db.add(Enrollment(room_id=sala.id, club_id=creador.id))
    if invitado is not None:
        db.add(Enrollment(room_id=sala.id, club_id=invitado.id))     # sala completa
    db.commit()
    return sala


@pytest.fixture
def como():
    """Mock de autenticación: como(club_id) simula a ese club logueado."""

    def _como(club_id: str) -> None:
        app.dependency_overrides[get_current_club] = lambda: SimpleNamespace(id=club_id)

    yield _como
    app.dependency_overrides.pop(get_current_club, None)


@pytest.fixture
def anfitrion(db: Session) -> Club:
    return crear_club(db, "anfitrion")


@pytest.fixture
def visitante(db: Session) -> Club:
    return crear_club(db, "visitante")


def ids(respuesta) -> list[str]:
    return [sala["roomId"] for sala in respuesta.json()]


# --- GET /api/friendly/rooms/public ---


def test_sin_token_devuelve_401(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


def test_sin_salas_devuelve_lista_vacia(client: TestClient, como, visitante: Club) -> None:
    como(visitante.id)

    r = client.get(URL)

    assert r.status_code == 200
    assert r.json() == []


def test_lista_la_sala_en_espera_con_los_campos_del_contrato(
    client: TestClient, db: Session, como, anfitrion: Club, visitante: Club
) -> None:
    sala = crear_sala(db, anfitrion)
    como(visitante.id)

    r = client.get(URL)

    assert r.status_code == 200
    assert r.json() == [{
        "roomId": sala.id, "status": "waitingGuest", "homeClub": anfitrion.id,
        "homeClubName": anfitrion.name, "createdAt": ANY,
    }]


def test_la_respuesta_no_expone_ningun_codigo(
    client: TestClient, db: Session, como, anfitrion: Club, visitante: Club
) -> None:
    crear_sala(db, anfitrion, code="ABC123")         # sala vieja que todavía tiene código guardado
    como(visitante.id)

    r = client.get(URL)

    assert ids(r)
    assert "roomCode" not in r.text
    assert "room_code" not in r.text
    assert "ABC123" not in r.text


def test_las_salas_se_ordenan_de_la_mas_reciente_a_la_mas_antigua(
    client: TestClient, db: Session, como, anfitrion: Club, visitante: Club
) -> None:
    ahora = datetime.now(timezone.utc)
    antigua = crear_sala(db, anfitrion, created_at=ahora - timedelta(hours=3))
    reciente = crear_sala(db, anfitrion, created_at=ahora - timedelta(hours=1))
    intermedia = crear_sala(db, anfitrion, created_at=ahora - timedelta(hours=2))
    como(visitante.id)

    assert ids(client.get(URL)) == [reciente.id, intermedia.id, antigua.id]


def test_excluye_las_salas_del_propio_club(
    client: TestClient, db: Session, como, anfitrion: Club, visitante: Club
) -> None:
    propia = crear_sala(db, visitante)
    ajena = crear_sala(db, anfitrion)
    como(visitante.id)

    assert ids(client.get(URL)) == [ajena.id]
    como(anfitrion.id)
    assert ids(client.get(URL)) == [propia.id]


@pytest.mark.parametrize("status", [
    ROOM_STATUS_READY_TO_START,       # completa: ya tiene visitante
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_CANCELLED,
])
def test_no_lista_salas_que_no_estan_en_espera(
    client: TestClient, db: Session, como, anfitrion: Club, visitante: Club, status: str
) -> None:
    otro = crear_club(db, "otro")
    crear_sala(db, anfitrion, status=status, invitado=otro if status == ROOM_STATUS_READY_TO_START else None)
    en_espera = crear_sala(db, anfitrion)
    como(visitante.id)

    assert ids(client.get(URL)) == [en_espera.id]


def test_no_lista_las_ligas(
    client: TestClient, db: Session, como, anfitrion: Club, visitante: Club
) -> None:
    db.add(Room(                                       # las ligas también arrancan en waiting_guest
        type=ROOM_TYPE_PUBLIC, name="Liga Publica", min_clubs=3, max_clubs=30,
        match_duration_minutes=10, status=ROOM_STATUS_WAITING_GUEST, creator_club_id=anfitrion.id,
    ))
    db.commit()
    como(visitante.id)

    assert client.get(URL).json() == []


# --- Crear una sala ya no genera código ---


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

def armar_solicitud(jugadores: list[Player], comportamiento: Behavior) -> CreateFriendlyRoomRequest:
    seleccion = lambda j: PlayerSelection(player_id=j.id, behavior_id=comportamiento.id)
    return CreateFriendlyRoomRequest(
        starters=[seleccion(j) for j in jugadores[:3]],
        substitutes=[seleccion(j) for j in jugadores[3:6]],
    )


def test_crear_la_sala_no_genera_ni_guarda_codigo(
    db: Session, anfitrion: Club, comportamiento: Behavior
) -> None:
    jugadores = crear_jugadores(db, anfitrion.id)
    anfitrion_id = anfitrion.id

    resultado = FriendlyService(db).create_room(anfitrion_id, armar_solicitud(jugadores, comportamiento))

    sala = db.get(Room, resultado.room_id)
    assert sala.code is None
    assert "room_code" not in resultado.model_dump()
    assert "roomCode" not in resultado.model_dump(by_alias=True)


def test_el_creador_queda_como_club_local_y_la_sala_en_espera(
    db: Session, anfitrion: Club, comportamiento: Behavior
) -> None:
    jugadores = crear_jugadores(db, anfitrion.id)
    anfitrion_id = anfitrion.id

    resultado = FriendlyService(db).create_room(anfitrion_id, armar_solicitud(jugadores, comportamiento))

    sala = db.get(Room, resultado.room_id)
    assert sala.creator_club_id == anfitrion_id
    assert resultado.home_club == anfitrion_id
    assert resultado.status == "waitingGuest"
    assert sala.status == ROOM_STATUS_WAITING_GUEST
    assert db.query(Enrollment).filter_by(room_id=sala.id, club_id=anfitrion_id).count() == 1


def test_la_sala_creada_aparece_en_el_listado_de_otro_club_pero_no_en_el_propio(
    client: TestClient, db: Session, como, anfitrion: Club, visitante: Club, comportamiento: Behavior
) -> None:
    jugadores = crear_jugadores(db, anfitrion.id)
    anfitrion_id, visitante_id = anfitrion.id, visitante.id
    resultado = FriendlyService(db).create_room(anfitrion_id, armar_solicitud(jugadores, comportamiento))

    como(visitante_id)
    assert ids(client.get(URL)) == [resultado.room_id]
    como(anfitrion_id)
    assert ids(client.get(URL)) == []

# --- agregado post-review ---

def test_si_falla_el_guardado_no_queda_nada_a_medias(
    db: Session, anfitrion: Club, comportamiento: Behavior, monkeypatch
) -> None:
    jugadores = crear_jugadores(db, anfitrion.id)
    anfitrion_id = anfitrion.id
    solicitud = armar_solicitud(jugadores, comportamiento)

    def falla():
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(db, "commit", falla)

    with pytest.raises(RuntimeError):
        FriendlyService(db).create_room(anfitrion_id, solicitud)

    assert db.query(Room).count() == 0
    assert db.query(Enrollment).count() == 0
    assert db.query(SquadEntry).count() == 0