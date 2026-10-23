from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.room import ROOM_STATUS_READY_TO_START, ROOM_STATUS_WAITING_GUEST
from app.models.user import User
from scripts.seed_friendly_rooms import HOME, PASSWORD, seed

"""Tests for the manual-testing seed script."""


def test_seed_creates_a_ready_room_and_a_waiting_room(db: Session) -> None:
    rooms = seed(db)

    assert rooms["ready"].status == ROOM_STATUS_READY_TO_START
    assert len(rooms["ready"].squad_entries) == 12
    assert rooms["waiting"].status == ROOM_STATUS_WAITING_GUEST
    assert len(rooms["waiting"].squad_entries) == 6


def test_seed_can_run_twice_reusing_the_users(db: Session) -> None:
    seed(db)
    seed(db)

    assert db.scalar(select(func.count()).select_from(User)) == 2


def test_seeded_user_can_log_in_and_start_the_ready_room(client: TestClient, db: Session) -> None:
    rooms = seed(db)

    login = client.post("/api/auth/login", json={"email": HOME["email"], "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(f"/api/friendly/rooms/{rooms['ready'].id}/start", headers=headers)

    assert login.status_code == 200
    assert response.status_code == 200
