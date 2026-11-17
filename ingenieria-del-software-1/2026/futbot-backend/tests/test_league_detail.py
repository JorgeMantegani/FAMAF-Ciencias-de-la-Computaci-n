"""Tests for GET /api/leagues/{league_id}."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.club import Club
from app.models.room import (
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_FRIENDLY,
    ROOM_TYPE_PRIVATE,
    Room,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from tests.test_league_join import make_club, make_league, make_players, squad_body
from tests.test_league_join import url as join_url

UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


def url(league_id: str) -> str:
    return f"/api/leagues/{league_id}"


@pytest.fixture
def creator(db: Session) -> Club:
    return make_club(db, "creador")


@pytest.fixture
def behavior(db: Session) -> Behavior:
    behavior = Behavior(
        name="Preprogramado", code="def behavior(player):\n    pass", is_preprogrammed=True
    )
    db.add(behavior)
    db.commit()
    return behavior


# --- Happy path ---


def test_returns_200_with_the_public_league_data(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    league = make_league(db, creator, max_clubs=8)

    r = client.get(url(league.id), headers=auth_headers)

    assert r.status_code == 200, r.json()
    assert r.json() == {
        "leagueId": league.id,
        "name": "Liga de Prueba",
        "isPrivate": False,
        "status": "waitingGuest",
        "minClubs": 3,
        "maxClubs": 8,
        "enrolledClubs": 1,
        "matchDurationMinutes": 10,
        "isEnrolled": False,
        "mySquad": None,
    }


def test_creator_is_enrolled(
    client: TestClient, db: Session, auth_headers, club: Club,
) -> None:
    league = make_league(db, club)

    r = client.get(url(league.id), headers=auth_headers)

    assert r.json()["isEnrolled"] is True


def test_joining_updates_enrolled_clubs_and_returns_the_own_squad(
    client: TestClient, db: Session, auth_headers, club: Club, creator: Club,
    behavior: Behavior,
) -> None:
    league = make_league(db, creator)
    players = make_players(db, club.id)
    before = client.get(url(league.id), headers=auth_headers).json()

    joined = client.post(
        join_url(league.id), json=squad_body(players, behavior), headers=auth_headers
    )
    after = client.get(url(league.id), headers=auth_headers).json()

    assert joined.status_code == 200
    assert (before["enrolledClubs"], before["isEnrolled"]) == (1, False)
    assert (after["enrolledClubs"], after["isEnrolled"]) == (2, True)
    squad = after["mySquad"]
    assert [p["role"] for p in squad] == [ROLE_STARTER] * 3 + [ROLE_SUBSTITUTE] * 3
    assert {p["playerId"] for p in squad[:3]} == {p.id for p in players[:3]}
    assert {p["playerId"] for p in squad[3:]} == {p.id for p in players[3:]}
    assert squad[0] == {
        "playerId": squad[0]["playerId"],
        "name": next(p.name for p in players if p.id == squad[0]["playerId"]),
        "role": ROLE_STARTER,
        "behaviorId": behavior.id,
        "behaviorName": behavior.name,
    }


def test_my_squad_excludes_other_clubs_players(
    client: TestClient, db: Session, auth_headers, club: Club, creator: Club,
    behavior: Behavior,
) -> None:
    league = make_league(db, creator)
    rivals = make_players(db, creator.id, prefix="Rival")
    db.add_all(
        SquadEntry(room_id=league.id, player_id=p.id, behavior_id=behavior.id,
                   role=ROLE_STARTER if i < 3 else ROLE_SUBSTITUTE)
        for i, p in enumerate(rivals)
    )
    db.commit()
    players = make_players(db, club.id)
    client.post(join_url(league.id), json=squad_body(players, behavior), headers=auth_headers)

    squad = client.get(url(league.id), headers=auth_headers).json()["mySquad"]

    assert {p["playerId"] for p in squad} == {p.id for p in players}


# --- Privacy and format ---


def test_private_league_hides_password_and_code(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    league = make_league(
        db, creator, name="Liga Privada", type=ROOM_TYPE_PRIVATE,
        password_hash="hash-secreto", code="ABC123",
    )

    r = client.get(url(league.id), headers=auth_headers)

    assert r.status_code == 200
    assert r.json()["isPrivate"] is True
    assert set(r.json()) == {
        "leagueId", "name", "isPrivate", "status", "minClubs", "maxClubs",
        "enrolledClubs", "matchDurationMinutes", "isEnrolled", "mySquad",
    }
    assert "hash-secreto" not in r.text
    assert "ABC123" not in r.text


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ROOM_STATUS_WAITING_GUEST, "waitingGuest"),
        (ROOM_STATUS_READY_TO_START, "readyToStart"),
        (ROOM_STATUS_IN_PROGRESS, "inProgress"),
    ],
)
def test_status_is_camel_case(
    client: TestClient, db: Session, auth_headers, creator: Club, status: str, expected: str,
) -> None:
    league = make_league(db, creator, status=status)

    r = client.get(url(league.id), headers=auth_headers)

    assert r.json()["status"] == expected


# --- Errors ---


def test_unknown_league_returns_404(client: TestClient, auth_headers) -> None:
    r = client.get(url(UNKNOWN_ID), headers=auth_headers)

    assert r.status_code == 404
    assert r.json()["error_code"] == "LEAGUE_NOT_FOUND"


def test_friendly_room_returns_404(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    room = Room(type=ROOM_TYPE_FRIENDLY, min_clubs=2, max_clubs=2,
                match_duration_minutes=10, creator_club_id=creator.id)
    db.add(room)
    db.commit()

    r = client.get(url(room.id), headers=auth_headers)

    assert r.status_code == 404
    assert r.json()["error_code"] == "LEAGUE_NOT_FOUND"


def test_without_token_returns_401(client: TestClient, db: Session, creator: Club) -> None:
    league = make_league(db, creator)

    r = client.get(url(league.id))

    assert r.status_code == 401
