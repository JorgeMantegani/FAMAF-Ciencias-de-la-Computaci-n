"""Tests for POST /api/leagues/{league_id}/join."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import ahora_utc as utc_now
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import (
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_TYPE_FRIENDLY,
    ROOM_TYPE_PRIVATE,
    ROOM_TYPE_PUBLIC,
    Room,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.models.user import User
from app.ws.leagues_events import register_league_events
from app.ws.leagues_hub import leagues_hub

PASSWORD = "secreta"
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"
BEHAVIOR_CODE = "def behavior(player):\n    pass"


# --- Builders ---


def make_club(db: Session, name: str) -> Club:
    user = User(username=name, email=f"{name}@futbot.test", password_hash="hash-de-prueba")
    user.club = Club(name=f"Club {name}")
    db.add(user)
    db.commit()
    return user.club


def make_league(db: Session, creator: Club, name: str = "Liga de Prueba", **overrides) -> Room:
    """League with only its creator enrolled."""
    fields = {
        "type": ROOM_TYPE_PUBLIC,
        "name": name,
        "min_clubs": 3,
        "max_clubs": 4,
        "match_duration_minutes": 10,
        "creator_club_id": creator.id,
        **overrides,
    }
    league = Room(**fields)
    db.add(league)
    db.flush()
    db.add(Enrollment(room_id=league.id, club_id=creator.id))
    db.commit()
    return league


def make_players(
    db: Session, club_id: str, count: int = 6, prefix: str = "Jugador"
) -> list[Player]:
    players = [
        Player(club_id=club_id, name=f"{prefix} {i}",
               power=60, agility=60, control=60, speed=60, strength=60)
        for i in range(count)
    ]
    db.add_all(players)
    db.commit()
    return players


def squad_body(players: list[Player], behavior: Behavior, **extra) -> dict:
    return {
        "titulares": [{"playerId": p.id, "behaviorId": behavior.id} for p in players[:3]],
        "suplentes": [{"playerId": p.id, "behaviorId": behavior.id} for p in players[3:6]],
        **extra,
    }


def url(league_id: str) -> str:
    return f"/api/leagues/{league_id}/join"


def is_enrolled(db: Session, league_id: str, club_id: str) -> bool:
    return db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.room_id == league_id, Enrollment.club_id == club_id)
    ) == 1


# --- Fixtures ---


@pytest.fixture
def creator(db: Session) -> Club:
    return make_club(db, "creador")


@pytest.fixture
def league(db: Session, creator: Club) -> Room:
    return make_league(db, creator)


@pytest.fixture
def private_league(db: Session, creator: Club) -> Room:
    return make_league(
        db, creator, name="Liga Privada",
        type=ROOM_TYPE_PRIVATE, password_hash=hash_password(PASSWORD),
    )


@pytest.fixture
def players(db: Session, club: Club) -> list[Player]:
    return make_players(db, club.id)


@pytest.fixture
def behavior(db: Session) -> Behavior:
    behavior = Behavior(name="Preprogramado", code=BEHAVIOR_CODE, is_preprogrammed=True)
    db.add(behavior)
    db.commit()
    return behavior


@pytest.fixture
def list_notice(monkeypatch) -> MagicMock:
    register_league_events()
    notice = MagicMock()
    monkeypatch.setattr(leagues_hub, "notify_changed", notice)
    return notice


# --- Happy path ---


def test_join_returns_200_with_the_contract_fields(
    client: TestClient, db: Session, auth_headers, club: Club, league: Room,
    players: list[Player], behavior: Behavior,
) -> None:
    r = client.post(url(league.id), json=squad_body(players, behavior), headers=auth_headers)

    assert r.status_code == 200, r.json()
    enrollment = db.scalar(
        select(Enrollment).where(Enrollment.room_id == league.id, Enrollment.club_id == club.id)
    )
    assert r.json() == {"enrollmentId": enrollment.id, "clubId": club.id, "leagueId": league.id}


def test_join_stores_the_six_player_squad(
    client: TestClient, db: Session, auth_headers, league: Room,
    players: list[Player], behavior: Behavior,
) -> None:
    client.post(url(league.id), json=squad_body(players, behavior), headers=auth_headers)

    entries = db.scalars(select(SquadEntry).where(SquadEntry.room_id == league.id)).all()
    assert {e.player_id for e in entries} == {p.id for p in players}
    assert sorted(e.role for e in entries) == [ROLE_STARTER] * 3 + [ROLE_SUBSTITUTE] * 3
    assert all(e.behavior_id == behavior.id for e in entries)


def test_public_league_ignores_the_password(
    client: TestClient, auth_headers, league: Room, players: list[Player], behavior: Behavior,
) -> None:
    body = squad_body(players, behavior, password="cualquiera")

    r = client.post(url(league.id), json=body, headers=auth_headers)

    assert r.status_code == 200


# --- League ---


def test_unknown_league_returns_404(
    client: TestClient, auth_headers, players: list[Player], behavior: Behavior,
) -> None:
    r = client.post(url(UNKNOWN_ID), json=squad_body(players, behavior), headers=auth_headers)

    assert r.status_code == 404
    assert r.json()["error_code"] == "LEAGUE_NOT_FOUND"


def test_friendly_room_is_not_a_league(
    client: TestClient, db: Session, auth_headers, creator: Club,
    players: list[Player], behavior: Behavior,
) -> None:
    room = Room(type=ROOM_TYPE_FRIENDLY, min_clubs=2, max_clubs=2,
                match_duration_minutes=10, creator_club_id=creator.id)
    db.add(room)
    db.commit()

    r = client.post(url(room.id), json=squad_body(players, behavior), headers=auth_headers)

    assert r.status_code == 404
    assert r.json()["error_code"] == "LEAGUE_NOT_FOUND"


def test_started_league_returns_400(
    client: TestClient, db: Session, auth_headers, club: Club, league: Room,
    players: list[Player], behavior: Behavior,
) -> None:
    league.status = ROOM_STATUS_IN_PROGRESS
    db.commit()

    r = client.post(url(league.id), json=squad_body(players, behavior), headers=auth_headers)

    assert r.status_code == 400
    assert r.json()["error_code"] == "LEAGUE_NOT_OPEN"
    assert not is_enrolled(db, league.id, club.id)


def test_full_league_returns_400_and_does_not_enroll(
    client: TestClient, db: Session, auth_headers, club: Club, creator: Club,
    players: list[Player], behavior: Behavior,
) -> None:
    league = make_league(db, creator, max_clubs=3)
    for name in ("rival1", "rival2"):
        db.add(Enrollment(room_id=league.id, club_id=make_club(db, name).id))
    db.commit()

    r = client.post(url(league.id), json=squad_body(players, behavior), headers=auth_headers)

    assert r.status_code == 400
    assert r.json()["error_code"] == "LEAGUE_FULL"
    assert not is_enrolled(db, league.id, club.id)
    assert db.scalars(select(SquadEntry).where(SquadEntry.room_id == league.id)).all() == []


# --- Club limits ---


def test_club_already_in_two_active_leagues_returns_400(
    client: TestClient, db: Session, auth_headers, club: Club, creator: Club, league: Room,
    players: list[Player], behavior: Behavior,
) -> None:
    for name in ("Liga A", "Liga B"):
        other = make_league(db, creator, name=name)
        db.add(Enrollment(room_id=other.id, club_id=club.id))
    db.commit()

    r = client.post(url(league.id), json=squad_body(players, behavior), headers=auth_headers)

    assert r.status_code == 400
    assert r.json()["error_code"] == "LEAGUE_LIMIT_REACHED"
    assert not is_enrolled(db, league.id, club.id)


def test_finished_leagues_do_not_count_toward_the_limit(
    client: TestClient, db: Session, auth_headers, club: Club, creator: Club, league: Room,
    players: list[Player], behavior: Behavior,
) -> None:
    for name in ("Liga A", "Liga B"):
        other = make_league(db, creator, name=name, status=ROOM_STATUS_FINISHED)
        db.add(Enrollment(room_id=other.id, club_id=club.id))
    db.commit()

    r = client.post(url(league.id), json=squad_body(players, behavior), headers=auth_headers)

    assert r.status_code == 200


def test_joining_twice_returns_400_and_keeps_the_original_squad(
    client: TestClient, db: Session, auth_headers, club: Club, league: Room,
    players: list[Player], behavior: Behavior,
) -> None:
    first = client.post(url(league.id), json=squad_body(players, behavior), headers=auth_headers)
    others = make_players(db, club.id, prefix="Otro")

    r = client.post(url(league.id), json=squad_body(others, behavior), headers=auth_headers)

    assert first.status_code == 200
    assert r.status_code == 400
    assert r.json()["error_code"] == "ALREADY_IN_LEAGUE"
    squad = db.scalars(select(SquadEntry.player_id).where(SquadEntry.room_id == league.id)).all()
    assert set(squad) == {p.id for p in players}


# --- Password ---


@pytest.mark.parametrize("extra", [{"password": "incorrecta"}, {}])
def test_private_league_with_wrong_or_missing_password_returns_400(
    client: TestClient, db: Session, auth_headers, club: Club, private_league: Room,
    players: list[Player], behavior: Behavior, extra: dict,
) -> None:
    body = squad_body(players, behavior, **extra)

    r = client.post(url(private_league.id), json=body, headers=auth_headers)

    assert r.status_code == 400
    assert r.json()["error_code"] == "WRONG_LEAGUE_PASSWORD"
    assert not is_enrolled(db, private_league.id, club.id)


def test_private_league_with_right_password_returns_200(
    client: TestClient, auth_headers, private_league: Room,
    players: list[Player], behavior: Behavior,
) -> None:
    body = squad_body(players, behavior, password=PASSWORD)

    r = client.post(url(private_league.id), json=body, headers=auth_headers)

    assert r.status_code == 200


# --- Squad ---


@pytest.mark.parametrize("problem", ["foreign", "unknown", "deleted", "repeated"])
def test_invalid_player_returns_400(
    client: TestClient, db: Session, auth_headers, club: Club, creator: Club, league: Room,
    players: list[Player], behavior: Behavior, problem: str,
) -> None:
    body = squad_body(players, behavior)
    last = body["suplentes"][-1]
    if problem == "foreign":
        last["playerId"] = make_players(db, creator.id, count=1, prefix="Ajeno")[0].id
    elif problem == "unknown":
        last["playerId"] = UNKNOWN_ID
    elif problem == "deleted":
        players[-1].deleted_at = utc_now()
        db.commit()
    else:
        last["playerId"] = players[0].id

    r = client.post(url(league.id), json=body, headers=auth_headers)

    assert r.status_code == 400
    assert r.json()["error_code"] == "INVALID_SQUAD"
    assert not is_enrolled(db, league.id, club.id)


@pytest.mark.parametrize("problem", ["foreign", "deleted"])
def test_invalid_behavior_returns_400(
    client: TestClient, db: Session, auth_headers, club: Club, creator: Club, league: Room,
    players: list[Player], behavior: Behavior, problem: str,
) -> None:
    if problem == "foreign":
        invalid = Behavior(club_id=creator.id, name="Ajeno", code=BEHAVIOR_CODE)
    else:
        invalid = Behavior(name="Borrado", code=BEHAVIOR_CODE, is_preprogrammed=True,
                           deleted_at=utc_now())
    db.add(invalid)
    db.commit()
    body = squad_body(players, behavior)
    body["suplentes"][-1]["behaviorId"] = invalid.id

    r = client.post(url(league.id), json=body, headers=auth_headers)

    assert r.status_code == 400
    assert r.json()["error_code"] == "INVALID_SQUAD"
    assert not is_enrolled(db, league.id, club.id)


def test_own_behavior_is_accepted(
    client: TestClient, db: Session, auth_headers, club: Club, league: Room,
    players: list[Player],
) -> None:
    own = Behavior(club_id=club.id, name="Propio", code=BEHAVIOR_CODE)
    db.add(own)
    db.commit()

    r = client.post(url(league.id), json=squad_body(players, own), headers=auth_headers)

    assert r.status_code == 200


def test_wrong_squad_size_returns_422(
    client: TestClient, auth_headers, league: Room, players: list[Player], behavior: Behavior,
) -> None:
    body = squad_body(players, behavior)
    body["titulares"] = body["titulares"][:2]

    r = client.post(url(league.id), json=body, headers=auth_headers)

    assert r.status_code == 422


# --- League list notice ---


def test_join_refreshes_the_league_list_once(
    client: TestClient, auth_headers, league: Room, players: list[Player], behavior: Behavior,
    list_notice: MagicMock,
) -> None:
    league_id, body = league.id, squad_body(players, behavior)
    list_notice.reset_mock()

    r = client.post(url(league_id), json=body, headers=auth_headers)

    assert r.status_code == 200
    list_notice.assert_called_once()


def test_join_rejected_after_the_lock_does_not_refresh_the_league_list(
    client: TestClient, db: Session, auth_headers, creator: Club,
    players: list[Player], behavior: Behavior, list_notice: MagicMock,
) -> None:
    league = make_league(db, creator, max_clubs=3)
    for name in ("rival1", "rival2"):
        db.add(Enrollment(room_id=league.id, club_id=make_club(db, name).id))
    db.commit()
    league_id, body = league.id, squad_body(players, behavior)
    list_notice.reset_mock()

    r = client.post(url(league_id), json=body, headers=auth_headers)

    assert r.json()["error_code"] == "LEAGUE_FULL"
    list_notice.assert_not_called()


# --- Auth ---


def test_without_token_returns_401(
    client: TestClient, league: Room, players: list[Player], behavior: Behavior,
) -> None:
    r = client.post(url(league.id), json=squad_body(players, behavior))

    assert r.status_code == 401
