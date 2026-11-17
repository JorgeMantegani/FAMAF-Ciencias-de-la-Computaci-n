import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.models.club import Club
from app.models.match import ESTADO_FINISHED, Match
from app.models.room import ROOM_STATUS_CANCELLED
from app.ws.leagues_hub import leagues_hub
from tests.test_list_leagues import crear_club, crear_liga

"""Tests del canal /ws/leagues."""

URL = "/ws/leagues"
AUTH = {"type": "auth", "token": "token-ok"}


@pytest.fixture(autouse=True)
def limpiar_hub():
    leagues_hub.filters.clear()          # el hub es global: evita que un test contamine a otro
    leagues_hub.standings_subscribers.clear()
    yield
    leagues_hub.filters.clear()
    leagues_hub.standings_subscribers.clear()


@pytest.fixture(autouse=True)
def sesion_del_hub(db: Session, monkeypatch):
    # El hub abre su propia sesión: se la redirige a la base temporal del test
    monkeypatch.setattr("app.ws.leagues_hub.SessionLocal", sessionmaker(bind=db.get_bind(), autoflush=False))


@pytest.fixture
def token_valido(monkeypatch):
    monkeypatch.setattr(
        "app.routers.leagues_ws.get_user_from_token",
        lambda db, token: object() if token == "token-ok" else None,
    )


@pytest.fixture
def creador(db: Session) -> Club:
    return crear_club(db, "creador")


def nombres(message: dict) -> list[str]:
    return [league["name"] for league in message["leagues"]]


# --- Autenticación ---


def test_token_invalido_cierra_con_4401_y_no_se_suscribe(client: TestClient, token_valido) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json({"type": "auth", "token": "otro"})
            ws.receive_json()

    assert error.value.code == 4401
    assert len(leagues_hub.filters) == 0


def test_token_basura_cierra_con_4401_con_la_autenticacion_real(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json({"type": "auth", "token": "esto-no-es-un-jwt"})
            ws.receive_json()

    assert error.value.code == 4401


@pytest.mark.parametrize("primero", [{"type": "search", "name": "x"}, [1, 2], "texto"])
def test_un_primer_mensaje_que_no_es_auth_cierra_con_4401(client: TestClient, token_valido, primero) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json(primero)
            ws.receive_json()

    assert error.value.code == 4401

@pytest.mark.parametrize("token", [123, None, ["x"], {"a": 1}, True])
def test_un_token_que_no_es_texto_cierra_con_4401(client: TestClient, token) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(URL) as ws:
            ws.send_json({"type": "auth", "token": token})
            ws.receive_json()

    assert error.value.code == 4401
    assert len(leagues_hub.filters) == 0


# --- Listado inicial ---


def test_el_listado_inicial_trae_solo_ligas_publicas_no_canceladas(
    client: TestClient, db: Session, token_valido, creador: Club
) -> None:
    publica = crear_liga(db, creador, "Liga Publica")
    crear_liga(db, creador, "Liga Privada", privada=True)
    crear_liga(db, creador, "Liga Cancelada", status=ROOM_STATUS_CANCELLED)
    publica_id = publica.id

    with client.websocket_connect(URL) as ws:
        ws.send_json(AUTH)

        assert ws.receive_json() == {
            "type": "leagues",
            "name": "",
            "leagues": [{
                "id": publica_id, "name": "Liga Publica", "participantsCount": 0,
                "started": False, "isPrivate": False, "hasPenaltyShootout": False,
            }],
        }
        assert len(leagues_hub.filters) == 1       # quedó suscripto

    assert len(leagues_hub.filters) == 0           # al desconectarse se da de baja


def test_sin_ligas_envia_un_listado_vacio(client: TestClient, token_valido) -> None:
    with client.websocket_connect(URL) as ws:
        ws.send_json(AUTH)

        assert ws.receive_json() == {"type": "leagues", "name": "", "leagues": []}


def test_standings_ws_sends_initial_table_and_subscribes(
    client: TestClient, db: Session, creador: Club, monkeypatch
) -> None:
    visitante = crear_club(db, "visitante")
    liga = crear_liga(db, creador, "Liga en vivo", inscriptos=(creador, visitante))
    monkeypatch.setattr(
        "app.routers.leagues.get_user_from_token",
        lambda db, token: object() if token == "token-ok" else None,
    )

    with client.websocket_connect(
        f"/api/leagues/{liga.id}/standings/ws"
    ) as websocket:
        websocket.send_json(AUTH)
        message = websocket.receive_json()
        assert message["type"] == "standings"
        assert message["league_id"] == liga.id
        assert len(message["standings"]) == 2
        assert liga.id in leagues_hub.standings_subscribers.values()

    assert liga.id not in leagues_hub.standings_subscribers.values()


def test_finishing_a_league_match_broadcasts_updated_standings(
    db: Session, creador: Club
) -> None:
    visitante = crear_club(db, "visitante")
    liga = crear_liga(db, creador, "Liga en vivo", inscriptos=(creador, visitante))
    partido = Match(
        room_id=liga.id,
        home_club_id=creador.id,
        away_club_id=visitante.id,
        status=ESTADO_FINISHED,
        home_goals=2,
        away_goals=1,
        duration_seconds=600,
    )
    db.add(partido)
    db.commit()
    websocket = AsyncMock()
    leagues_hub.add_standings_subscriber(websocket, liga.id)

    asyncio.run(leagues_hub.broadcast_standings_updated(liga.id, partido.id))

    message = websocket.send_json.await_args.args[0]
    assert message["type"] == "standings_updated"
    assert message["league_id"] == liga.id
    assert message["match_id"] == partido.id
    assert {row["club_id"]: row["points"] for row in message["standings"]} == {
        creador.id: 3,
        visitante.id: 0,
    }


# --- Búsqueda ---


def test_buscar_filtra_ignora_espacios_y_devuelve_el_filtro_aplicado(
    client: TestClient, db: Session, token_valido, creador: Club
) -> None:
    for nombre in ("Liga Norte", "Copa Sur", "Liga del Sur"):
        crear_liga(db, creador, nombre)

    with client.websocket_connect(URL) as ws:
        ws.send_json(AUTH)
        ws.receive_json()
        ws.send_json({"type": "search", "name": "  sUr  "})

        message = ws.receive_json()

    assert message["name"] == "sUr"
    assert nombres(message) == ["Copa Sur", "Liga del Sur"]


def test_buscar_ignora_mayusculas_en_tildes_y_enie(
    client: TestClient, db: Session, token_valido, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Ñandú")
    crear_liga(db, creador, "Otra Liga")

    with client.websocket_connect(URL) as ws:
        ws.send_json(AUTH)
        ws.receive_json()
        ws.send_json({"type": "search", "name": "ÑANDÚ"})

        assert nombres(ws.receive_json()) == ["Liga Ñandú"]


def test_buscar_sin_coincidencias_y_volver_a_buscar_vacio(
    client: TestClient, db: Session, token_valido, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Norte")

    with client.websocket_connect(URL) as ws:
        ws.send_json(AUTH)
        ws.receive_json()

        ws.send_json({"type": "search", "name": "zzz"})
        assert ws.receive_json()["leagues"] == []

        ws.send_json({"type": "search", "name": ""})
        assert nombres(ws.receive_json()) == ["Liga Norte"]


def test_la_busqueda_no_revela_ligas_privadas(
    client: TestClient, db: Session, token_valido, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Secreta", privada=True)

    with client.websocket_connect(URL) as ws:
        ws.send_json(AUTH)
        ws.receive_json()
        ws.send_json({"type": "search", "name": "secreta"})

        assert ws.receive_json()["leagues"] == []


def test_un_filtro_invalido_responde_error_y_el_canal_sigue_funcionando(
    client: TestClient, db: Session, token_valido, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Norte")

    with client.websocket_connect(URL) as ws:
        ws.send_json(AUTH)
        ws.receive_json()

        ws.send_json({"type": "search", "name": "x" * 81})
        assert ws.receive_json()["type"] == "error"

        ws.send_json({"type": "search", "name": 123})
        assert ws.receive_json()["type"] == "error"

        ws.send_json({"type": "search", "name": "norte"})
        assert nombres(ws.receive_json()) == ["Liga Norte"]


def test_un_mensaje_que_no_es_json_responde_error_y_el_canal_sigue_funcionando(
    client: TestClient, token_valido
) -> None:
    with client.websocket_connect(URL) as ws:
        ws.send_json(AUTH)
        ws.receive_json()

        ws.send_text("esto no es json")
        assert ws.receive_json()["type"] == "error"

        ws.send_json({"type": "search", "name": ""})
        assert ws.receive_json()["type"] == "leagues"


# --- Avisos de cambios (el hub) ---


def test_broadcast_envia_a_cada_suscripto_su_listado_con_su_filtro(
    db: Session, creador: Club
) -> None:
    for nombre in ("Liga Norte", "Copa Sur"):
        crear_liga(db, creador, nombre)
    todos, solo_sur = AsyncMock(), AsyncMock()
    leagues_hub.add(todos)
    leagues_hub.add(solo_sur)
    leagues_hub.set_filter(solo_sur, "sur")

    asyncio.run(leagues_hub.broadcast())

    mensaje_todos = todos.send_json.await_args.args[0]
    mensaje_sur = solo_sur.send_json.await_args.args[0]
    assert nombres(mensaje_todos) == ["Copa Sur", "Liga Norte"]
    assert (mensaje_sur["name"], nombres(mensaje_sur)) == ("sur", ["Copa Sur"])


def test_broadcast_refleja_las_ligas_creadas_despues_de_conectarse(
    db: Session, creador: Club
) -> None:
    suscripto = AsyncMock()
    leagues_hub.add(suscripto)
    asyncio.run(leagues_hub.broadcast())
    assert suscripto.send_json.await_args.args[0]["leagues"] == []

    crear_liga(db, creador, "Liga Nueva")
    asyncio.run(leagues_hub.broadcast())

    assert nombres(suscripto.send_json.await_args.args[0]) == ["Liga Nueva"]


def test_broadcast_descarta_las_conexiones_caidas_y_sigue_con_las_demas(db: Session) -> None:
    viva, caida = AsyncMock(), AsyncMock()
    caida.send_json.side_effect = RuntimeError("conexion cerrada")
    leagues_hub.add(viva)
    leagues_hub.add(caida)

    asyncio.run(leagues_hub.broadcast())

    viva.send_json.assert_awaited_once()
    assert viva in leagues_hub.filters
    assert caida not in leagues_hub.filters


def test_broadcast_sin_suscriptos_no_consulta_la_base(monkeypatch) -> None:
    consultas = []