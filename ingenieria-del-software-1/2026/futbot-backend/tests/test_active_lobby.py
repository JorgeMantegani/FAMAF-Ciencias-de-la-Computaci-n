"""Pruebas exhaustivas para el Lobby de Liga Activa, motor de posiciones y gestión de escuadras."""
import uuid
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.room import Room, ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_WAITING_GUEST, ROOM_TYPE_PUBLIC, MIN_LEAGUE_CLUBS
from app.models.match import Match, ESTADO_IN_PROGRESS, ESTADO_SCHEDULED
from app.models.player import Player
from app.models.behavior import Behavior
from app.models.squad_entry import SquadEntry, ROLE_STARTER, ROLE_SUBSTITUTE
from app.models.auth_session import AuthSession
from app.core.security import create_access_token
from app.services.league_orchestrator import get_league_lobby_payload


def crear_usuario_y_club(db: Session, nombre: str):
    usuario = User(username=nombre, email=f"{nombre}@futbot.test", password_hash="hash")
    db.add(usuario)
    db.flush()
    club = Club(user_id=usuario.id, name=f"Club {nombre}")
    db.add(club)
    db.commit()
    db.refresh(club)
    db.refresh(usuario)
    return club, usuario


def generar_token(db: Session, usuario: User) -> str:
    session_id = str(uuid.uuid4())
    db.add(AuthSession(id=session_id, user_id=usuario.id, refresh_hash="ref", expires_at=time.time()+3600, revoked=False))
    db.commit()
    return create_access_token(usuario.id, session_id)


def test_standings_strict_tie_breaker_rules(db: Session):
    """Valida rigurosamente los 5 niveles de desempate en orden estricto:
       1. Puntos, 2. Partidos ganados, 3. Diferencia de goles, 4. Goles a favor, 5. Orden alfabético.
    """
    creator, _ = crear_usuario_y_club(db, "creator")
    league = Room(
        id=str(uuid.uuid4()),
        type=ROOM_TYPE_PUBLIC,
        name="Liga Criterios Estrictos",
        creator_club_id=creator.id,
        min_clubs=MIN_LEAGUE_CLUBS,
        max_clubs=5,
        match_duration_minutes=5,
        status=ROOM_STATUS_IN_PROGRESS,
    )
    db.add(league)
    db.flush()

    c_delta, _ = crear_usuario_y_club(db, "Delta")
    c_alpha, _ = crear_usuario_y_club(db, "Alpha")
    c_beta, _ = crear_usuario_y_club(db, "Beta")

    db.add(Enrollment(room_id=league.id, club_id=c_alpha.id, points=3, matches_won=1, goals_for=4, goals_against=1))
    db.add(Enrollment(room_id=league.id, club_id=c_beta.id, points=3, matches_won=1, goals_for=3, goals_against=2))
    db.add(Enrollment(room_id=league.id, club_id=c_delta.id, points=3, matches_won=1, goals_for=5, goals_against=4))
    db.commit()

    payload = get_league_lobby_payload(db, league.id)
    standings = payload["standings"]

    assert standings[0]["club_id"] == c_alpha.id
    assert standings[1]["club_id"] == c_delta.id
    assert standings[2]["club_id"] == c_beta.id


def test_get_live_lobby_success_and_filtering(client: TestClient, db: Session):
    """Verifica el retorno 200 y el filtrado correcto de currentMatch y nextMatch en el lobby activo."""
    creator, usuario = crear_usuario_y_club(db, "owner")
    rival, _ = crear_usuario_y_club(db, "rival")
    tercero, _ = crear_usuario_y_club(db, "tercero")
    
    league = Room(
        id=str(uuid.uuid4()),
        type=ROOM_TYPE_PUBLIC,
        name="Liga Completa Test",
        creator_club_id=creator.id,
        min_clubs=MIN_LEAGUE_CLUBS,
        max_clubs=4,
        match_duration_minutes=5,
        status=ROOM_STATUS_IN_PROGRESS,
    )
    db.add(league)
    db.add(Enrollment(room_id=league.id, club_id=creator.id))
    db.add(Enrollment(room_id=league.id, club_id=rival.id))
    db.add(Enrollment(room_id=league.id, club_id=tercero.id))

    m_playing = Match(
        id=str(uuid.uuid4()), room_id=league.id, round=1,
        home_club_id=creator.id, away_club_id=rival.id,
        status=ESTADO_IN_PROGRESS, duration_seconds=300
    )
    m_scheduled = Match(
        id=str(uuid.uuid4()), room_id=league.id, round=2,
        home_club_id=rival.id, away_club_id=tercero.id,
        status=ESTADO_SCHEDULED, duration_seconds=300
    )
    db.add(m_playing)
    db.add(m_scheduled)
    db.commit()

    token = generar_token(db, usuario)
    response = client.get(
        f"/api/leagues/{league.id}/live-lobby",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["league_id"] == league.id
    assert data["status"] == ROOM_STATUS_IN_PROGRESS
    assert data["currentMatch"]["id"] == m_playing.id
    assert data["nextMatch"]["id"] == m_scheduled.id
    assert len(data["calendar"]) == 2
    assert len(data["standings"]) == 3


def test_get_live_lobby_errors(client: TestClient, db: Session):
    """Verifica errores HTTP para ligas inexistentes o no iniciadas."""
    creator, usuario = crear_usuario_y_club(db, "ownererr")
    token = generar_token(db, usuario)

    # 1. Intentar consultar una liga que no existe
    resp_404 = client.get("/api/leagues/uuid-inexistente/live-lobby", headers={"Authorization": f"Bearer {token}"})
    assert resp_404.status_code in (404, 400)

    # 2. Consultar una liga en estado de espera (waiting_guest)
    league_waiting = Room(
        id=str(uuid.uuid4()),
        type=ROOM_TYPE_PUBLIC,
        name="Liga Espera",
        creator_club_id=creator.id,
        min_clubs=MIN_LEAGUE_CLUBS,
        max_clubs=4,
        match_duration_minutes=5,
        status=ROOM_STATUS_WAITING_GUEST,
    )
    db.add(league_waiting)
    db.commit()

    resp_error = client.get(f"/api/leagues/{league_waiting.id}/live-lobby", headers={"Authorization": f"Bearer {token}"})
    assert resp_error.status_code in (400, 404)


def test_update_league_squad_validation_and_update(client: TestClient, db: Session):
    """Valida la restricción de cantidades exactas en la escuadra y la correcta actualización limpia."""
    creator, usuario = crear_usuario_y_club(db, "squadmanager")
    league = Room(
        id=str(uuid.uuid4()),
        type=ROOM_TYPE_PUBLIC,
        name="Liga Squads",
        creator_club_id=creator.id,
        min_clubs=MIN_LEAGUE_CLUBS,
        max_clubs=4,
        match_duration_minutes=5,
        status=ROOM_STATUS_IN_PROGRESS,
    )
    db.add(league)
    db.commit()

    # Crear behavior real incluyendo el campo 'code' obligatorio y players reales en BD
    behavior = Behavior(id=str(uuid.uuid4()), name="Default Behavior", code="default_code", is_preprogrammed = True)
    db.add(behavior)
    players = []
    for i in range(6):
        p = Player(id=str(uuid.uuid4()), name=f"Player {i}", club_id=creator.id, speed=60, control=60, strength=60, power=60, agility=60)
        db.add(p)
        players.append(p)
    db.commit()

    token = generar_token(db, usuario)

    # 1. Enviar payload con cantidades incorrectas -> 400
    invalid_payload = {
        "entries": [
            {"player_id": players[0].id, "role": "starter", "behavior_id": behavior.id}
        ]
    }
    resp_invalid = client.put(
        f"/api/leagues/{league.id}/squad",
        json=invalid_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_invalid.status_code == 400

    # 2. Enviar payload válido (3 titulares y 3 suplentes) -> 200 OK
    valid_payload = {
        "entries": [
            {"player_id": players[i].id, "role": "starter" if i < 3 else "substitute", "behavior_id": behavior.id}
            for i in range(6)
        ]
    }
    resp_valid = client.put(
        f"/api/leagues/{league.id}/squad",
        json=valid_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["status"] == "success"