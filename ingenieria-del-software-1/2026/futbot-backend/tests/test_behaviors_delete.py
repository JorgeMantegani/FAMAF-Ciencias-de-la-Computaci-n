from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.behavior import Behavior
from app.models.room import Room, ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED
from app.models.squad_entry import SquadEntry

def test_delete_behavior_success(client: TestClient, db: Session, auth_headers, club):
    # Comportamiento propio sin dependencias
    behavior = Behavior(club_id=club.id, name="Estrategia Vieja", code="pass", is_preprogrammed=False)
    db.add(behavior)
    db.commit()

    response = client.delete(f"/api/behaviors/{behavior.id}", headers=auth_headers)
    assert response.status_code == 204

    db.expire_all()
    deleted_behavior = db.query(Behavior).filter(Behavior.id == behavior.id).first()
    assert deleted_behavior is not None
    assert deleted_behavior.deleted_at is not None

def test_delete_behavior_conflict_in_active_room(client: TestClient, db: Session, auth_headers, club, club_players):
    behavior = Behavior(club_id=club.id, name="Estrategia Activa", code="pass", is_preprogrammed=False)
    db.add(behavior)
    db.commit()

    # Sala activa (in_progress)
    room = Room(type="friendly", creator_club_id=club.id, min_clubs=2, max_clubs=2, match_duration_minutes=5, status=ROOM_STATUS_IN_PROGRESS)
    db.add(room)
    db.commit()

    # Plantilla usando el comportamiento en sala activa
    squad_entry = SquadEntry(room_id=room.id, player_id=club_players[0].id, behavior_id=behavior.id, role="starter")
    db.add(squad_entry)
    db.commit()

    response = client.delete(f"/api/behaviors/{behavior.id}", headers=auth_headers)
    assert response.status_code == 409
    
    db.expire_all()
    deleted_behavior = db.query(Behavior).filter(Behavior.id == behavior.id).first()
    assert deleted_behavior is not None
    assert deleted_behavior.deleted_at is None

def test_delete_behavior_success_if_room_finished(client: TestClient, db: Session, auth_headers, club, club_players):
    behavior = Behavior(club_id=club.id, name="Estrategia Histórica", code="pass", is_preprogrammed=False)
    db.add(behavior)
    db.commit()

    # Sala finalizada (finished) -> No debe bloquear la eliminación
    room = Room(type="friendly", creator_club_id=club.id, min_clubs=2, max_clubs=2, match_duration_minutes=5, status=ROOM_STATUS_FINISHED)
    db.add(room)
    db.commit()

    squad_entry = SquadEntry(room_id=room.id, player_id=club_players[0].id, behavior_id=behavior.id, role="starter")
    db.add(squad_entry)
    db.commit()

    response = client.delete(f"/api/behaviors/{behavior.id}", headers=auth_headers)
    assert response.status_code == 204
    
    db.expire_all()
    deleted_behavior = db.query(Behavior).filter(Behavior.id == behavior.id).first()
    assert deleted_behavior is not None
    assert deleted_behavior.deleted_at is not None

def test_delete_behavior_forbidden_other_club(client: TestClient, db: Session, auth_headers, other_club):
    # Comportamiento perteneciente a otro club
    other_behavior = Behavior(club_id=other_club.id, name="Estrategia Ajena", code="pass", is_preprogrammed=False)
    db.add(other_behavior)
    db.commit()

    response = client.delete(f"/api/behaviors/{other_behavior.id}", headers=auth_headers)
    assert response.status_code == 403