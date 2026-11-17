import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.room import (
    MIN_LEAGUE_CLUBS,
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_FRIENDLY,
    ROOM_TYPE_PUBLIC,
    Room,
)
from app.services.auth import start_session


@pytest.fixture
def token(db: Session, club: Club) -> str:
    return start_session(db, club.user).access_token


def charm_room(db: Session, club_id: str, room_type: str, status: str, code: str, name: str = None):
    """Helper para crear salas e inscribir al club cumpliendo los constraints del modelo."""
    is_friendly = (room_type == ROOM_TYPE_FRIENDLY)
    room = Room(
        type=room_type,
        status=status,
        code=code,
        name=name if not is_friendly else None,
        creator_club_id=club_id,
        min_clubs=2 if is_friendly else MIN_LEAGUE_CLUBS,
        max_clubs=2 if is_friendly else 10,
        match_duration_minutes=5
    )
    db.add(room)
    db.commit()
    db.refresh(room)

    enrollment = Enrollment(
        room_id=room.id,
        club_id=club_id
    )
    db.add(enrollment)
    db.commit()
    return room


def test_ws_active_rooms_success_and_payload(
    client: TestClient, db: Session, club: Club, token: str
):
    """
    Criterio: Conexión válida acepta y envía el listado inicial con id y code,
    separando amistosos y ligas, y excluyendo finalizadas/canceladas.
    """
    room_friendly = charm_room(
        db, club.id, ROOM_TYPE_FRIENDLY, ROOM_STATUS_WAITING_GUEST, "F-0001"
    )
    room_league = charm_room(
        db, club.id, ROOM_TYPE_PUBLIC, ROOM_STATUS_WAITING_GUEST, "L-0001", name="Liga Test"
    )
    charm_room(
        db, club.id, ROOM_TYPE_PUBLIC, ROOM_STATUS_FINISHED, "FIN-0001", name="Liga Terminada"
    )
    charm_room(db, club.id, ROOM_TYPE_FRIENDLY, ROOM_STATUS_CANCELLED, "CAN-0001")
    # The endpoint closes the shared session, so read the ids before connecting.
    friendly_id, league_id = room_friendly.id, room_league.id

    with client.websocket_connect(f"/ws/rooms/active?token={token}") as websocket:
        data = websocket.receive_json()

        assert isinstance(data, list)
        assert len(data) == 2

        room_ids = {r["id"] for r in data}
        assert friendly_id in room_ids
        assert league_id in room_ids

        for r in data:
            assert "id" in r
            assert "code" in r
            assert "type" in r
            assert "status" in r


def test_ws_active_rooms_empty_list(client: TestClient, token: str):
    """
    Criterio: Si no hay salas en curso, se devuelve un listado vacío [].
    """
    with client.websocket_connect(f"/ws/rooms/active?token={token}") as websocket:
        data = websocket.receive_json()
        assert isinstance(data, list)
        assert len(data) == 0


def test_ws_active_rooms_unauthorized(client: TestClient):
    """
    Criterio: Token inválido o ausente rechaza la conexión.
    """
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/rooms/active?token=token_invalido"):
            pass
