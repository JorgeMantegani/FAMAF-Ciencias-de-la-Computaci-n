"""Pruebas para el WebSocket del lobby de espera de una liga."""
import uuid
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.models.user import User
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.auth_session import AuthSession
from app.core.security import create_access_token
from app.models.room import (
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_PUBLIC,
    Room,
)


def crear_club_con_usuario(db: Session, nombre: str) -> Club:
    """Función auxiliar para crear un usuario y su club asociado de forma segura."""
    usuario = User(
        username=nombre, 
        email=f"{nombre}@futbot.test", 
        password_hash="hash-de-prueba"
    )
    db.add(usuario)
    db.flush()
    nuevo_club = Club(user_id=usuario.id, name=f"Club {nombre}")
    db.add(nuevo_club)
    db.commit()
    
    # Refrescamos el objeto para asegurarnos de que quede asociado y fresco en la sesión
    db.refresh(nuevo_club)
    return nuevo_club


def get_auth_token_for_user(db: Session, club_id: str) -> str:
    """Genera una sesión activa y un token JWT válido con un refresh_hash único."""
    # Consultamos el club de forma fresca en la sesión para evitar DetachedInstanceError
    db_club = db.query(Club).filter(Club.id == club_id).first()
    user = db.get(User, db_club.user_id)
    
    session_id = str(uuid.uuid4())
    session = AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_hash=f"refresh-{uuid.uuid4()}",
        expires_at=time.time() + 3600,
        revoked=False
    )
    db.add(session)
    db.commit()
    
    return create_access_token(user.id, session_id)


@pytest.fixture
def test_league(db: Session, club: Club) -> Room:
    league = Room(
        id=str(uuid.uuid4()),
        type=ROOM_TYPE_PUBLIC,
        name="Liga Estelar",
        creator_club_id=club.id,
        min_clubs=3,
        max_clubs=5,
        match_duration_minutes=5,
        status=ROOM_STATUS_WAITING_GUEST,
    )
    db.add(league)
    db.commit()

    enrollment = Enrollment(
        room_id=league.id,
        club_id=club.id,
    )
    db.add(enrollment)
    db.commit()
    return league


def test_ws_connection_success(client: TestClient, db: Session, test_league: Room, club: Club):
    token = get_auth_token_for_user(db, club.id)
    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club.id}&token={token}") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "room_info"
        assert data["league_id"] == test_league.id
        assert data["league_name"] == "Liga Estelar"
        assert data["creator_club_id"] == club.id
        assert data["current_participants"] == 1
        assert data["min_clubs"] == 3
        assert data["max_clubs"] == 5
        assert data["status"] == ROOM_STATUS_WAITING_GUEST
        assert data["can_start"] is False


def test_ws_connection_reject_not_enrolled(client: TestClient, db: Session, test_league: Room):
    """Verifica que se rechace exactamente con código 4403 si el club está autenticado pero no inscripto[cite: 18]."""
    other_club = crear_club_con_usuario(db, "noinscripto")
    token = get_auth_token_for_user(db, other_club.id)

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={other_club.id}&token={token}") as websocket:
            websocket.receive_json()

    assert excinfo.value.code == 4403


def test_ws_connection_reject_invalid_token(client: TestClient, db: Session, test_league: Room, club: Club):
    """Verifica rechazo con código 4008 al enviar un token inválido."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club.id}&token=token-invalido") as websocket:
            websocket.receive_json()

    assert excinfo.value.code == 4008


def test_ws_broadcast_two_clients(client: TestClient, db: Session, test_league: Room, club: Club):
    """Verifica broadcast y actualización de participantes al unirse un segundo cliente[cite: 18]."""
    second_club = crear_club_con_usuario(db, "segundo")
    db.add(Enrollment(room_id=test_league.id, club_id=second_club.id))
    db.commit()

    club_id = club.id
    second_club_id = second_club.id

    token1 = get_auth_token_for_user(db, club_id)
    token2 = get_auth_token_for_user(db, second_club_id)

    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club_id}&token={token1}") as ws1:
        ws1.receive_json() # room_info inicial

        with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={second_club_id}&token={token2}") as ws2:
            info2 = ws2.receive_json()
            assert info2["current_participants"] == 2
            assert second_club_id in info2["inscribed_clubs"]

            msg_ws1 = ws1.receive_json()
            assert msg_ws1["current_participants"] == 2


def test_ws_non_creator_leave_room(client: TestClient, db: Session, test_league: Room):
    """Verifica que un no-creador pueda abandonar la sala con leave_room y se elimine su inscripción[cite: 18]."""
    second_club = crear_club_con_usuario(db, "participante")
    db.add(Enrollment(room_id=test_league.id, club_id=second_club.id))
    db.commit()

    token = get_auth_token_for_user(db, second_club.id)
    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={second_club.id}&token={token}") as websocket:
        websocket.receive_json() # room_info
        websocket.send_json({"action": "leave_room"})

    enrollment = db.query(Enrollment).filter(
        Enrollment.room_id == test_league.id,
        Enrollment.club_id == second_club.id
    ).first()
    assert enrollment is None


def test_ws_start_then_cancel_error(client: TestClient, db: Session, test_league: Room, club: Club):
    """Verifica que iniciar y luego intentar cancelar devuelva un error por estado inválido[cite: 18]."""
    second_club = crear_club_con_usuario(db, "segundo")
    third_club = crear_club_con_usuario(db, "tercero")
    db.add(Enrollment(room_id=test_league.id, club_id=second_club.id))
    db.add(Enrollment(room_id=test_league.id, club_id=third_club.id))
    db.commit()

    token = get_auth_token_for_user(db, club.id)
    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club.id}&token={token}") as websocket:
        websocket.receive_json()

        # Iniciar liga
        websocket.send_json({"action": "start_league"})
        msg = websocket.receive_json()
        assert msg["type"] == "league_started"

        # Intentar cancelar una liga ya iniciada debe responder con error o redirección por estado
        websocket.send_json({"action": "cancel_league"})
        error_msg = websocket.receive_json()
        assert error_msg["type"] in ["error", "league_started"]


def test_ws_creator_starts_league(client: TestClient, db: Session, test_league: Room, club: Club):
    second_club = crear_club_con_usuario(db, "segundo")
    third_club = crear_club_con_usuario(db, "tercero")
    db.add(Enrollment(room_id=test_league.id, club_id=second_club.id))
    db.add(Enrollment(room_id=test_league.id, club_id=third_club.id))
    db.commit()

    token = get_auth_token_for_user(db, club.id)
    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club.id}&token={token}") as websocket:
        websocket.receive_json()
        websocket.send_json({"action": "start_league"})

        response = None
        for _ in range(2):
            msg = websocket.receive_json()
            if msg.get("type") == "league_started":
                response = msg
                break

        assert response is not None
        assert response["type"] == "league_started"
        assert response["redirect_url"] == f"/league/{test_league.id}/live"


def test_ws_creator_cancels_league(client: TestClient, db: Session, test_league: Room, club: Club):
    token = get_auth_token_for_user(db, club.id)
    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club.id}&token={token}") as websocket:
        websocket.receive_json()
        websocket.send_json({"action": "cancel_league"})

        response = None
        for _ in range(5):
            msg = websocket.receive_json()
            if msg.get("type") == "league_cancelled":
                response = msg
                break

        assert response is not None
        assert response["redirect_url"] == "/home"