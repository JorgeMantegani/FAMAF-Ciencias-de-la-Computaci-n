import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.models.club import Club
from app.models.room import (
    Room,
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_PUBLIC,
)
from app.ws.leagues_events import register_league_events
from app.ws.public_friendly_hub import public_friendly_hub
from tests.test_public_friendly import crear_club, crear_sala

"""Tests del canal /ws/friendly-rooms/public."""

URL = "/ws/friendly-rooms/public"


@pytest.fixture(autouse=True)
def limpiar_hub():
    public_friendly_hub.clubs.clear()    # el hub es global: evita que un test contamine a otro
    yield
    public_friendly_hub.clubs.clear()


@pytest.fixture(autouse=True)
def sesion_del_hub(db: Session, monkeypatch):
    # El hub abre su propia sesión: se la redirige a la base temporal del test
    monkeypatch.setattr(
        "app.ws.public_friendly_hub.SessionLocal", sessionmaker(bind=db.get_bind(), autoflush=False)
    )


@pytest.fixture
def tokens(monkeypatch):
    """Tokens de prueba: 'club:<id>' es de un usuario con ese club; 'sin-club', de uno sin club."""

    def fake(db, token):
        if token == "sin-club":
            return SimpleNamespace(club=None)
        if isinstance(token, str) and token.startswith("club:"):
            return SimpleNamespace(club=SimpleNamespace(id=token.removeprefix("club:")))
        return None

    monkeypatch.setattr("app.routers.public_friendly_ws.get_user_from_token", fake)


def auth(club_id: str) -> dict:
    return {"type": "auth", "token": f"club:{club_id}"}


def room_ids(message: dict) -> list[str]:
    return [room["roomId"] for room in message["rooms"]]


# --- Autenticación ---


def test_token_invalido_cierra_con_4401_y_no_se_suscribe(client: TestClient, tokens) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json({"type": "auth", "token": "otro"})
            ws.receive_json()

    assert error.value.code == 4401
    assert len(public_friendly_hub.clubs) == 0


def test_token_basura_cierra_con_4401_con_la_autenticacion_real(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json({"type": "auth", "token": "esto-no-es-un-jwt"})
            ws.receive_json()

    assert error.value.code == 4401


@pytest.mark.parametrize("token", [123, None, ["x"], {"a": 1}, True])
def test_un_token_que_no_es_texto_cierra_con_4401(client: TestClient, token) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json({"type": "auth", "token": token})
            ws.receive_json()

    assert error.value.code == 4401
    assert len(public_friendly_hub.clubs) == 0


@pytest.mark.parametrize("primero", [{"type": "search", "name": "x"}, [1, 2], "texto"])
def test_un_primer_mensaje_que_no_es_auth_cierra_con_4401(client: TestClient, tokens, primero) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json(primero)
            ws.receive_json()

    assert error.value.code == 4401


def test_un_usuario_sin_club_cierra_con_4401(client: TestClient, tokens) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json({"type": "auth", "token": "sin-club"})
            ws.receive_json()

    assert error.value.code == 4401
    assert len(public_friendly_hub.clubs) == 0


# --- Listado inicial ---


def test_sin_salas_envia_un_listado_vacio(client: TestClient, db: Session, tokens) -> None:
    visitante_id = crear_club(db, "visitante").id

    with client.websocket_connect(URL) as ws:
        ws.send_json(auth(visitante_id))

        assert ws.receive_json() == {"type": "rooms", "rooms": []}


def test_el_listado_inicial_trae_solo_salas_en_espera_de_otros_clubes(
    client: TestClient, db: Session, tokens
) -> None:
    anfitrion = crear_club(db, "anfitrion")
    visitante = crear_club(db, "visitante")
    otro = crear_club(db, "otro")
    visible = crear_sala(db, anfitrion)
    crear_sala(db, visitante)                                                  # propia: no se lista
    crear_sala(db, anfitrion, status=ROOM_STATUS_READY_TO_START, invitado=otro)   # completa
    crear_sala(db, anfitrion, status=ROOM_STATUS_IN_PROGRESS)
    crear_sala(db, anfitrion, status=ROOM_STATUS_FINISHED)
    crear_sala(db, anfitrion, status=ROOM_STATUS_CANCELLED)
    db.add(Room(                                                               # una liga también arranca en waiting_guest
        type=ROOM_TYPE_PUBLIC, name="Liga Publica", min_clubs=3, max_clubs=30,
        match_duration_minutes=10, status=ROOM_STATUS_WAITING_GUEST, creator_club_id=anfitrion.id,
    ))
    db.commit()
    esperado = {
        "roomId": visible.id, "status": "waitingGuest", "homeClub": anfitrion.id,
        "homeClubName": anfitrion.name, "createdAt": ANY,
    }
    mensaje_auth = auth(visitante.id)

    with client.websocket_connect(URL) as ws:
        ws.send_json(mensaje_auth)

        assert ws.receive_json() == {"type": "rooms", "rooms": [esperado]}
        assert len(public_friendly_hub.clubs) == 1     # quedó suscripto

    assert len(public_friendly_hub.clubs) == 0         # al desconectarse se da de baja


def test_las_salas_llegan_de_la_mas_reciente_a_la_mas_antigua(
    client: TestClient, db: Session, tokens
) -> None:
    anfitrion = crear_club(db, "anfitrion")
    visitante = crear_club(db, "visitante")
    ahora = datetime.now(timezone.utc)
    antigua = crear_sala(db, anfitrion, created_at=ahora - timedelta(hours=3))
    reciente = crear_sala(db, anfitrion, created_at=ahora - timedelta(hours=1))
    intermedia = crear_sala(db, anfitrion, created_at=ahora - timedelta(hours=2))
    esperado = [reciente.id, intermedia.id, antigua.id]
    mensaje_auth = auth(visitante.id)

    with client.websocket_connect(URL) as ws:
        ws.send_json(mensaje_auth)

        assert room_ids(ws.receive_json()) == esperado


def test_el_mensaje_no_expone_ningun_codigo(client: TestClient, db: Session, tokens) -> None:
    anfitrion = crear_club(db, "anfitrion")
    visitante_id = crear_club(db, "visitante").id
    crear_sala(db, anfitrion, code="ABC123")           # sala vieja que todavía tiene código guardado

    with client.websocket_connect(URL) as ws:
        ws.send_json(auth(visitante_id))
        texto = json.dumps(ws.receive_json())

    assert "homeClubName" in texto
    assert "roomCode" not in texto
    assert "room_code" not in texto
    assert "ABC123" not in texto


# --- Avisos de cambios (el hub) ---


def test_broadcast_envia_a_cada_club_su_listado_sin_sus_propias_salas(db: Session) -> None:
    club_a, club_b, club_c = (crear_club(db, nombre) for nombre in ("a", "b", "c"))
    sala_a, sala_b = crear_sala(db, club_a), crear_sala(db, club_b)
    ids = {"a": club_a.id, "b": club_b.id, "c": club_c.id}
    de_a, de_b = sala_a.id, sala_b.id
    ws_a, ws_b, ws_c = AsyncMock(), AsyncMock(), AsyncMock()
    public_friendly_hub.add(ws_a, ids["a"])
    public_friendly_hub.add(ws_b, ids["b"])
    public_friendly_hub.add(ws_c, ids["c"])

    asyncio.run(public_friendly_hub.broadcast())

    def recibidas(ws):
        return set(room_ids(ws.send_json.await_args.args[0]))

    assert recibidas(ws_a) == {de_b}            # no ve su propia sala
    assert recibidas(ws_b) == {de_a}
    assert recibidas(ws_c) == {de_a, de_b}


def test_broadcast_refleja_las_salas_creadas_despues_de_conectarse(db: Session) -> None:
    anfitrion = crear_club(db, "anfitrion")
    visitante_id = crear_club(db, "visitante").id
    suscripto = AsyncMock()
    public_friendly_hub.add(suscripto, visitante_id)
    asyncio.run(public_friendly_hub.broadcast())
    assert suscripto.send_json.await_args.args[0]["rooms"] == []

    nueva_id = crear_sala(db, anfitrion).id
    asyncio.run(public_friendly_hub.broadcast())

    assert room_ids(suscripto.send_json.await_args.args[0]) == [nueva_id]


def test_una_sala_que_se_completa_deja_de_listarse(db: Session) -> None:
    anfitrion = crear_club(db, "anfitrion")
    visitante = crear_club(db, "visitante")
    sala = crear_sala(db, anfitrion)
    visitante_id = visitante.id
    suscripto = AsyncMock()
    public_friendly_hub.add(suscripto, visitante_id)
    asyncio.run(public_friendly_hub.broadcast())
    assert len(suscripto.send_json.await_args.args[0]["rooms"]) == 1

    sala.status = ROOM_STATUS_READY_TO_START      # se unió un rival
    db.commit()
    asyncio.run(public_friendly_hub.broadcast())

    assert suscripto.send_json.await_args.args[0]["rooms"] == []


def test_broadcast_descarta_las_conexiones_cerradas_y_sigue_con_las_demas(db: Session) -> None:
    club_id = crear_club(db, "club").id
    viva, desconectada, ya_cerrada = AsyncMock(), AsyncMock(), AsyncMock()
    desconectada.send_json.side_effect = WebSocketDisconnect(code=1006)
    ya_cerrada.send_json.side_effect = RuntimeError('Cannot call "send" once a close message has been sent.')
    for ws in (viva, desconectada, ya_cerrada):
        public_friendly_hub.add(ws, club_id)

    asyncio.run(public_friendly_hub.broadcast())

    viva.send_json.assert_awaited_once()
    assert viva in public_friendly_hub.clubs
    assert desconectada not in public_friendly_hub.clubs
    assert ya_cerrada not in public_friendly_hub.clubs


def test_un_error_inesperado_no_se_oculta_pero_las_demas_conexiones_reciben_el_listado(db: Session) -> None:
    club_id = crear_club(db, "club").id
    rota, viva = AsyncMock(), AsyncMock()
    rota.send_json.side_effect = ValueError("bug")
    public_friendly_hub.add(rota, club_id)
    public_friendly_hub.add(viva, club_id)

    with pytest.raises(ValueError):
        asyncio.run(public_friendly_hub.broadcast())

    viva.send_json.assert_awaited_once()              # el resto igual recibió el listado
    assert rota in public_friendly_hub.clubs          # y la conexión con el bug no se da de baja en silencio

def test_broadcast_sin_suscriptos_no_consulta_la_base(monkeypatch) -> None:
    consultas = []
    monkeypatch.setattr("app.ws.public_friendly_hub.load_rooms", lambda: consultas.append(1) or [])

    asyncio.run(public_friendly_hub.broadcast())

    assert consultas == []


# --- El aviso automático llega a este canal ---


def test_confirmar_una_sala_avisa_al_canal_de_amistosos(db: Session, monkeypatch) -> None:
    register_league_events()
    notify = MagicMock()
    monkeypatch.setattr(public_friendly_hub, "notify_changed", notify)
    anfitrion = crear_club(db, "anfitrion")
    notify.assert_not_called()                     # crear usuarios y clubes no cambia el listado

    crear_sala(db, anfitrion)

    notify.assert_called_once()