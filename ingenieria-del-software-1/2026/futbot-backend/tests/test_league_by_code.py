"""Tests for GET /api/leagues/by-code/{code}."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.club import Club
from app.models.room import ROOM_TYPE_FRIENDLY, ROOM_TYPE_PRIVATE, Room
from tests.test_league_join import make_club, make_league

CODE = "a1b2c3d4"


def url(code: str) -> str:
    return f"/api/leagues/by-code/{code}"


@pytest.fixture
def creator(db: Session) -> Club:
    return make_club(db, "creador")


@pytest.fixture
def private_league(db: Session, creator: Club) -> Room:
    return make_league(
        db, creator, type=ROOM_TYPE_PRIVATE, code=CODE, password_hash=hash_password("secreta")
    )


def test_finds_a_private_league(
    client: TestClient, auth_headers, private_league: Room,
) -> None:
    r = client.get(url(CODE), headers=auth_headers)

    assert r.status_code == 200, r.json()
    assert r.json()["leagueId"] == private_league.id
    assert r.json()["isPrivate"] is True


def test_finds_a_public_league(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    league = make_league(db, creator, code=CODE)

    r = client.get(url(CODE), headers=auth_headers)

    assert r.status_code == 200, r.json()
    assert r.json()["leagueId"] == league.id
    assert r.json()["isPrivate"] is False


def test_returns_the_same_body_as_the_league_detail(
    client: TestClient, auth_headers, private_league: Room,
) -> None:
    r = client.get(url(CODE), headers=auth_headers)

    assert r.json() == client.get(f"/api/leagues/{private_league.id}", headers=auth_headers).json()


@pytest.mark.parametrize("typed_code", ["A1B2C3D4", "%20a1b2c3d4%20", "%20A1b2C3d4%20"])
def test_ignores_case_and_surrounding_spaces(
    client: TestClient, auth_headers, private_league: Room, typed_code: str,
) -> None:
    r = client.get(url(typed_code), headers=auth_headers)

    assert r.status_code == 200, r.json()
    assert r.json()["leagueId"] == private_league.id


def test_friendly_room_code_returns_404(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    # Lowercase like a league code: only the room type can stop the match.
    db.add(Room(type=ROOM_TYPE_FRIENDLY, code=CODE, min_clubs=2, max_clubs=2,
                match_duration_minutes=10, creator_club_id=creator.id))
    db.commit()

    r = client.get(url(CODE), headers=auth_headers)

    assert r.status_code == 404
    assert r.json()["error_code"] == "LEAGUE_NOT_FOUND"


def test_unknown_code_returns_404(client: TestClient, auth_headers) -> None:
    r = client.get(url(CODE), headers=auth_headers)

    assert r.status_code == 404
    assert r.json()["error_code"] == "LEAGUE_NOT_FOUND"


def test_without_token_returns_401(client: TestClient, private_league: Room) -> None:
    r = client.get(url(CODE))

    assert r.status_code == 401


def test_response_exposes_neither_password_hash_nor_code(
    client: TestClient, auth_headers, private_league: Room,
) -> None:
    body = client.get(url(CODE), headers=auth_headers).json()

    assert not {"passwordHash", "password_hash", "code", "codeToJoin"} & body.keys()
    assert CODE not in body.values()
    assert private_league.password_hash not in body.values()
