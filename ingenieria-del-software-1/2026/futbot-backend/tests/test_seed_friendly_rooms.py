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
    assert all(user.email_verified_at is not None for user in db.scalars(select(User)))


def test_seed_can_run_twice_reusing_the_users(db: Session) -> None:
    seed(db)
    verified_dates = {user.id: user.email_verified_at for user in db.scalars(select(User))}
    seed(db)

    assert db.scalar(select(func.count()).select_from(User)) == 2
    assert {user.id: user.email_verified_at for user in db.scalars(select(User))} == verified_dates


def test_seed_verifies_existing_demo_users(client: TestClient, db: Session) -> None:
    seed(db)
    for user in db.scalars(select(User)):
        user.email_verified_at = None
    db.commit()

    seed(db)

    assert db.scalar(select(func.count()).select_from(User)) == 2
    assert all(user.email_verified_at is not None for user in db.scalars(select(User)))
    login = client.post("/api/auth/login", json={"email": HOME["email"], "password": PASSWORD})
    assert login.status_code == 200, login.json()


def test_seeded_user_can_log_in_and_start_the_ready_room(client: TestClient, db: Session) -> None:
    rooms = seed(db)

    login = client.post("/api/auth/login", json={"email": HOME["email"], "password": PASSWORD})
    assert login.status_code == 200, login.json()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(f"/api/friendly/rooms/{rooms['ready'].id}/start", headers=headers)

    assert response.status_code == 200
