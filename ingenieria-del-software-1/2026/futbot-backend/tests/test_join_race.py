#
#   prueba uniones a amistoso al unisono
#
import threading
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import (
    Room,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_FRIENDLY,
)
from app.models.squad_entry import SquadEntry
from app.models.user import User
from app.schemas.friendly_room import JoinFriendlyRoomRequest
from app.services import friendly_service
from app.services.friendly_service import FriendlyService

"""Condiciones de carrera al unirse a un amistoso: el cupo visitante nunca se duplica."""


# --- Datos ---


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


def armar_solicitud(jugadores: list[Player], behavior_id: str) -> JoinFriendlyRoomRequest:
    seleccion = lambda j: {"playerId": j.id, "behaviorId": behavior_id}
    return JoinFriendlyRoomRequest.model_validate({
        "titulares": [seleccion(j) for j in jugadores[:3]],
        "suplentes": [seleccion(j) for j in jugadores[3:6]],
    })


@pytest.fixture
def escenario(db: Session) -> SimpleNamespace:
    """Una sala en espera (del anfitrión) y dos clubes que quieren unirse, cada uno con 6 jugadores."""
    anfitrion, club_a, club_b = (crear_club(db, nombre) for nombre in ("anfitrion", "a", "b"))
    comportamiento = Behavior(
        name="Preprogramado de prueba", code="def behavior(player):\n    pass", is_preprogrammed=True,
    )
    db.add(comportamiento)
    db.commit()
    jugadores_a = crear_jugadores(db, club_a.id)
    jugadores_b = crear_jugadores(db, club_b.id)

    sala = Room(
        type=ROOM_TYPE_FRIENDLY, min_clubs=2, max_clubs=2, match_duration_minutes=10,
        status=ROOM_STATUS_WAITING_GUEST, creator_club_id=anfitrion.id,
    )
    db.add(sala)
    db.flush()
    db.add(Enrollment(room_id=sala.id, club_id=anfitrion.id))
    db.commit()

    return SimpleNamespace(
        sala_id=sala.id, anfitrion_id=anfitrion.id, a_id=club_a.id, b_id=club_b.id,
        req_a=armar_solicitud(jugadores_a, comportamiento.id),
        req_b=armar_solicitud(jugadores_b, comportamiento.id),
        ids_jugadores_a={j.id for j in jugadores_a},
    )


@pytest.fixture
def sin_validar_plantilla(monkeypatch):
    # La validación de la plantilla tiene sus propios tests: acá solo interesa el cupo
    monkeypatch.setattr(friendly_service, "validate_squad_selection", lambda *args, **kwargs: None)


# --- Carrera forzada (determinista) ---


def test_si_otro_club_ocupa_el_cupo_en_medio_de_la_union_recibe_409_y_no_se_duplica(
    db: Session, engine, escenario, monkeypatch
) -> None:
    e = escenario
    rival_db = sessionmaker(bind=engine, autoflush=False)()
    rival_unido: list[bool] = []

    def validar(_db, club_id, starters, substitutes):
        # El club A ya pasó el chequeo de estado y está validando su plantilla:
        # justo ahí el club B se une y confirma.
        if club_id == e.a_id and not rival_unido:
            rival_unido.append(True)
            FriendlyService(rival_db).join_room(e.b_id, e.sala_id, e.req_b)

    monkeypatch.setattr(friendly_service, "validate_squad_selection", validar)
    try:
        with pytest.raises(HTTPException) as error:
            FriendlyService(db).join_room(e.a_id, e.sala_id, e.req_a)
    finally:
        rival_db.close()

    assert rival_unido == [True]                                   # la carrera realmente ocurrió
    assert error.value.status_code == 409
    assert error.value.detail["detail"] == "La sala ya no está disponible."

    db.expire_all()
    assert db.get(Room, e.sala_id).status == ROOM_STATUS_READY_TO_START
    inscriptos = [x.club_id for x in db.query(Enrollment).filter_by(room_id=e.sala_id)]
    assert sorted(inscriptos) == sorted([e.anfitrion_id, e.b_id])   # un solo visitante: B
    assert db.query(SquadEntry).filter(
        SquadEntry.room_id == e.sala_id, SquadEntry.player_id.in_(e.ids_jugadores_a)
    ).count() == 0                                                  # nada de la plantilla de A quedó guardado


def test_el_segundo_intento_posterior_recibe_409(db: Session, escenario, sin_validar_plantilla) -> None:
    e = escenario
    FriendlyService(db).join_room(e.a_id, e.sala_id, e.req_a)

    with pytest.raises(HTTPException) as error:
        FriendlyService(db).join_room(e.b_id, e.sala_id, e.req_b)

    assert error.value.status_code == 409
    assert db.query(Enrollment).filter_by(room_id=e.sala_id).count() == 2


# --- Concurrencia real ---


def test_dos_clubes_se_unen_a_la_vez_y_solo_uno_obtiene_el_cupo(
    db: Session, engine, escenario, sin_validar_plantilla
) -> None:
    e = escenario
    fabrica = sessionmaker(bind=engine, autoflush=False)
    arranque = threading.Barrier(2)                  # los dos hilos salen al mismo tiempo
    resultados: dict[str, int] = {}

    def unir(nombre: str, club_id: str, solicitud: JoinFriendlyRoomRequest) -> None:
        with fabrica() as sesion:                    # una sesión (y una conexión) por hilo
            arranque.wait(timeout=10)
            try:
                FriendlyService(sesion).join_room(club_id, e.sala_id, solicitud)
                resultados[nombre] = 200
            except HTTPException as error:
                resultados[nombre] = error.status_code

    hilos = [
        threading.Thread(target=unir, args=("a", e.a_id, e.req_a)),
        threading.Thread(target=unir, args=("b", e.b_id, e.req_b)),
    ]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert sorted(resultados.values()) == [200, 409]
    db.expire_all()
    assert db.query(Enrollment).filter_by(room_id=e.sala_id).count() == 2          # anfitrión + un solo visitante
    assert db.query(SquadEntry).filter_by(room_id=e.sala_id).count() == 6          # una sola plantilla


# --- Listado público ---


def test_tras_unirse_la_sala_deja_de_aparecer_en_el_listado_publico(
    db: Session, escenario, sin_validar_plantilla
) -> None:
    e = escenario
    assert [s.room_id for s in FriendlyService(db).list_public_rooms(club_id=e.b_id)] == [e.sala_id]

    FriendlyService(db).join_room(e.a_id, e.sala_id, e.req_a)

    assert FriendlyService(db).list_public_rooms(club_id=e.b_id) == []