from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.main import app
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.room import (
    Room,
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_FRIENDLY,
    ROOM_TYPE_PRIVATE,
    ROOM_TYPE_PUBLIC,
)
from app.models.user import User

"""Tests de GET /api/leagues."""

URL = "/api/leagues"
PASSWORD_HASH = "hash-de-prueba"


def crear_club(db: Session, nombre: str) -> Club:
    usuario = User(username=nombre, email=f"{nombre}@futbot.test", password_hash="hash-de-prueba")
    db.add(usuario)
    db.flush()
    club = Club(user_id=usuario.id, name=f"Club {nombre}")
    db.add(club)
    db.commit()
    return club


def crear_liga(
    db: Session,
    creador: Club,
    nombre: str,
    *,
    privada: bool = False,
    status: str = ROOM_STATUS_WAITING_GUEST,
    inscriptos: tuple[Club, ...] = (),
    has_penalty_shootout: bool = False,
) -> Room:
    liga = Room(
        type=ROOM_TYPE_PRIVATE if privada else ROOM_TYPE_PUBLIC,
        name=nombre, min_clubs=3, max_clubs=30, match_duration_minutes=10,
        status=status, creator_club_id=creador.id,
        password_hash=PASSWORD_HASH if privada else None,   # el CHECK exige contraseña solo en privadas
        has_penalty_shootout=has_penalty_shootout,
    )
    db.add(liga)
    db.flush()
    for club in inscriptos:
        db.add(Enrollment(room_id=liga.id, club_id=club.id))
    db.commit()
    return liga


@pytest.fixture
def autenticado():
    """Mock de autenticacion: el endpoint solo necesita que haya un usuario valido."""
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace()
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def creador(db: Session) -> Club:
    return crear_club(db, "creador")


def nombres(respuesta) -> list[str]:
    return [liga["name"] for liga in respuesta.json()]


# --- Autenticación ---


def test_sin_token_devuelve_401(client: TestClient) -> None:
    r = client.get(URL)

    assert r.status_code == 401


# --- Listado ---


def test_sin_ligas_devuelve_lista_vacia(client: TestClient, autenticado) -> None:
    r = client.get(URL)

    assert r.status_code == 200
    assert r.json() == []


def test_cada_liga_trae_los_campos_del_contrato(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    liga = crear_liga(db, creador, "Liga Norte", has_penalty_shootout=True)

    r = client.get(URL)

    assert r.status_code == 200
    assert r.json() == [{
        "id": liga.id, "name": "Liga Norte", "participantsCount": 0,
        "started": False, "isPrivate": False, "hasPenaltyShootout": True,
    }]


def test_participants_count_cuenta_los_clubes_inscriptos(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    inscriptos = tuple(crear_club(db, f"club{i}") for i in range(3))
    crear_liga(db, creador, "Liga Llena", inscriptos=inscriptos)
    crear_liga(db, creador, "Liga Vacia")

    por_nombre = {liga["name"]: liga["participantsCount"] for liga in client.get(URL).json()}

    assert por_nombre == {"Liga Llena": 3, "Liga Vacia": 0}


@pytest.mark.parametrize("status, iniciada", [
    (ROOM_STATUS_WAITING_GUEST, False),
    (ROOM_STATUS_IN_PROGRESS, True),
    (ROOM_STATUS_FINISHED, True),
])
def test_started_refleja_si_la_liga_ya_comenzo(
    client: TestClient, db: Session, autenticado, creador: Club, status: str, iniciada: bool
) -> None:
    crear_liga(db, creador, "Liga", status=status)

    assert client.get(URL).json()[0]["started"] is iniciada


def test_no_lista_los_amistosos(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Real")
    db.add(Room(
        type=ROOM_TYPE_FRIENDLY, min_clubs=2, max_clubs=2, match_duration_minutes=10,
        status=ROOM_STATUS_WAITING_GUEST, creator_club_id=creador.id, code="ABC123",
    ))
    db.commit()

    assert nombres(client.get(URL)) == ["Liga Real"]


def test_no_lista_las_ligas_canceladas(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Activa")
    crear_liga(db, creador, "Publica Cancelada", status=ROOM_STATUS_CANCELLED)
    crear_liga(db, creador, "Privada Cancelada", privada=True, status=ROOM_STATUS_CANCELLED)

    assert nombres(client.get(URL)) == ["Liga Activa"]


def test_las_ligas_se_ordenan_por_nombre_sin_distinguir_mayusculas(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    for nombre in ("beta", "Alfa", "delta", "Charlie"):
        crear_liga(db, creador, nombre)

    assert nombres(client.get(URL)) == ["Alfa", "beta", "Charlie", "delta"]


def test_no_lista_las_ligas_privadas(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Publica")
    crear_liga(db, creador, "Liga Privada", privada=True)

    r = client.get(URL)

    assert nombres(r) == ["Liga Publica"]
    assert r.json()[0]["isPrivate"] is False


# --- Filtro por nombre ---


def test_filtra_por_nombre_sin_distinguir_mayusculas_y_con_coincidencia_parcial(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    for nombre in ("Liga Norte", "Copa Sur", "Liga del Sur"):
        crear_liga(db, creador, nombre)

    r = client.get(URL, params={"name": "sUr"})

    assert r.status_code == 200
    assert sorted(nombres(r)) == ["Copa Sur", "Liga del Sur"]


@pytest.mark.parametrize("nombre, filtro", [
    ("Liga Ñandú", "ñandú"),
    ("Liga Ñandú", "ÑANDÚ"),
    ("Liga ñandú", "LIGA ÑANDÚ"),
    ("Copa Águila", "águila"),
    ("Copa águila", "ÁGUILA"),
    ("Liga Straße", "STRASSE"),
])
def test_el_filtro_ignora_mayusculas_en_tildes_y_enie(
    client: TestClient, db: Session, autenticado, creador: Club, nombre: str, filtro: str
) -> None:
    crear_liga(db, creador, nombre)
    crear_liga(db, creador, "Otra Liga")

    r = client.get(URL, params={"name": filtro})

    assert nombres(r) == [nombre]


def test_sin_coincidencias_devuelve_lista_vacia(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Norte")

    r = client.get(URL, params={"name": "inexistente"})

    assert r.status_code == 200
    assert r.json() == []


def test_filtro_vacio_o_con_espacios_devuelve_todas(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    for nombre in ("Liga A", "Liga B"):
        crear_liga(db, creador, nombre)

    assert len(client.get(URL, params={"name": ""}).json()) == 2
    assert len(client.get(URL, params={"name": "   "}).json()) == 2


def test_el_filtro_ignora_los_espacios_de_los_costados(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Norte")

    assert nombres(client.get(URL, params={"name": "  norte  "})) == ["Liga Norte"]


def test_los_caracteres_especiales_del_filtro_se_tratan_como_texto(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    for nombre in ("Liga Norte", "Liga 100%", "Liga A_B", "Liga AxB"):
        crear_liga(db, creador, nombre)

    assert nombres(client.get(URL, params={"name": "%"})) == ["Liga 100%"]
    assert nombres(client.get(URL, params={"name": "_"})) == ["Liga A_B"]


def test_el_filtro_no_devuelve_ligas_canceladas(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Cancelada", status=ROOM_STATUS_CANCELLED)

    assert client.get(URL, params={"name": "cancelada"}).json() == []


def test_filtro_de_80_caracteres_es_valido(client: TestClient, autenticado) -> None:
    assert client.get(URL, params={"name": "x" * 80}).status_code == 200


def test_filtro_demasiado_largo_devuelve_422(client: TestClient, autenticado) -> None:
    r = client.get(URL, params={"name": "x" * 81})

    assert r.status_code == 422


def test_el_filtro_no_revela_ligas_privadas(
    client: TestClient, db: Session, autenticado, creador: Club
) -> None:
    crear_liga(db, creador, "Liga Secreta", privada=True)

    r = client.get(URL, params={"name": "secreta"})

    assert r.status_code == 200
    assert r.json() == []