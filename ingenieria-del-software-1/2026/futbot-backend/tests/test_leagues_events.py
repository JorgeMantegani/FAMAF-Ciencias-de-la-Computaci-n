import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.models.room import (
    Room,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_PUBLIC,
)
from app.ws.leagues_events import register_league_events
from app.ws.leagues_hub import LeaguesHub, leagues_hub
from tests.test_list_leagues import crear_club, crear_liga

"""Tests del aviso automático de cambios en las ligas."""


@pytest.fixture
def notify(monkeypatch):
    register_league_events()
    mock = MagicMock()
    monkeypatch.setattr(leagues_hub, "notify_changed", mock)
    return mock


# --- Qué cambios avisan ---


def test_confirmar_una_sala_nueva_avisa(db: Session, notify) -> None:
    creador = crear_club(db, "creador")
    notify.assert_not_called()                      # crear usuarios y clubes no cambia el listado

    crear_liga(db, creador, "Liga Nueva")

    notify.assert_called_once()


def test_una_inscripcion_nueva_avisa(db: Session, notify) -> None:
    creador = crear_club(db, "creador")
    liga = crear_liga(db, creador, "Liga")
    otro = crear_club(db, "otro")
    notify.reset_mock()

    db.add(Enrollment(room_id=liga.id, club_id=otro.id))
    db.commit()

    notify.assert_called_once()


def test_cambiar_el_estado_de_una_liga_avisa(db: Session, notify) -> None:
    creador = crear_club(db, "creador")
    liga = crear_liga(db, creador, "Liga")
    notify.reset_mock()

    liga.status = ROOM_STATUS_IN_PROGRESS
    db.commit()

    notify.assert_called_once()


def test_borrar_una_liga_avisa(db: Session, notify) -> None:
    creador = crear_club(db, "creador")
    liga = crear_liga(db, creador, "Liga")
    notify.reset_mock()

    db.delete(liga)
    db.commit()

    notify.assert_called_once()


def test_un_update_masivo_avisa(db: Session, notify) -> None:
    creador = crear_club(db, "creador")
    liga_id = crear_liga(db, creador, "Liga").id
    notify.reset_mock()

    db.query(Room).filter(Room.id == liga_id).update(
        {Room.status: ROOM_STATUS_IN_PROGRESS}, synchronize_session=False
    )
    db.commit()

    notify.assert_called_once()


def test_varios_cambios_en_una_transaccion_avisan_una_sola_vez(db: Session, notify) -> None:
    creador = crear_club(db, "creador")
    notify.reset_mock()

    db.add(Room(
        type=ROOM_TYPE_PUBLIC, name="Liga A", min_clubs=3, max_clubs=30, match_duration_minutes=10,
        status=ROOM_STATUS_WAITING_GUEST, creator_club_id=creador.id,
    ))
    db.add(Room(
        type=ROOM_TYPE_PUBLIC, name="Liga B", min_clubs=3, max_clubs=30, match_duration_minutes=10,
        status=ROOM_STATUS_WAITING_GUEST, creator_club_id=creador.id,
    ))
    db.commit()

    notify.assert_called_once()


def test_un_rollback_no_avisa(db: Session, notify) -> None:
    creador = crear_club(db, "creador")
    notify.reset_mock()

    db.add(Room(
        type=ROOM_TYPE_PUBLIC, name="Liga Fallida", min_clubs=3, max_clubs=30, match_duration_minutes=10,
        status=ROOM_STATUS_WAITING_GUEST, creator_club_id=creador.id,
    ))
    db.flush()
    db.rollback()
    crear_club(db, "otro")                          # un commit posterior que no toca ligas

    notify.assert_not_called()


# --- notify_changed (el hub) ---


def test_notify_changed_programa_el_aviso_en_el_loop_desde_otro_hilo() -> None:
    async def escenario():
        hub = LeaguesHub()
        hub.bind_loop(asyncio.get_running_loop())
        hub.broadcast = AsyncMock()
        hub.add(AsyncMock())

        await asyncio.to_thread(hub.notify_changed)   # como lo haría un endpoint síncrono

        for _ in range(100):
            if hub.broadcast.await_count:
                break
            await asyncio.sleep(0.01)
        hub.broadcast.assert_awaited_once()

    asyncio.run(escenario())


def test_notify_changed_sin_loop_o_sin_suscriptos_no_hace_nada() -> None:
    hub = LeaguesHub()
    hub.broadcast = AsyncMock()
    hub.add(AsyncMock())

    hub.notify_changed()                              # sin loop: se ignora, sin error

    async def sin_suscriptos():
        otro = LeaguesHub()
        otro.bind_loop(asyncio.get_running_loop())
        otro.broadcast = AsyncMock()
        otro.notify_changed()                         # nadie mira el listado: no se programa nada
        await asyncio.sleep(0.05)
        otro.broadcast.assert_not_awaited()

    asyncio.run(sin_suscriptos())
    hub.broadcast.assert_not_awaited()