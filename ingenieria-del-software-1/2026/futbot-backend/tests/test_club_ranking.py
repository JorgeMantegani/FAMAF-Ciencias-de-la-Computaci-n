"""Reglas de ranking en servicio y contrato HTTP autenticado."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.auth_session import AuthSession
from app.models.club import Club
from app.models.user import User
from app.services.club_ranking import get_club_ranking


@pytest.fixture
def ranked_clubs(db, club):
    club.name = "Delta"
    club.ranking_points = 28
    clubs = {"Delta": club}
    # Inserción fuera de orden para detectar un ordenamiento incompleto.
    for name, points in [("Zulu", 50), ("Beta", 28), ("Alpha", 50), ("Omega", 0)]:
        user = User(username=name, email=f"{name}@test.com", password_hash="test")
        user.club = Club(name=name, ranking_points=points, avatar_url=f"{name}.png")
        db.add(user)
        clubs[name] = user.club
    db.commit()
    return clubs


def test_service_points_and_alphabetical_ties(db, ranked_clubs):
    result = get_club_ranking(db, ranked_clubs["Delta"].id)
    assert [item.club_name for item in result.items] == ["Alpha", "Zulu", "Beta", "Delta", "Omega"]
    assert [item.ranking_points for item in result.items] == [50, 50, 28, 28, 0]
    assert [item.position for item in result.items] == [1, 2, 3, 4, 5]
    assert result.user_club_ranking.position == 4
    assert result.user_club_ranking.ranking_points == 28
    assert result.total_clubs == 5
    assert result.total_pages == 1


def test_service_pagination_keeps_global_positions(db, ranked_clubs):
    club_id = ranked_clubs["Delta"].id
    first = get_club_ranking(db, club_id, page=1, size=2)
    second = get_club_ranking(db, club_id, page=2, size=2)
    last = get_club_ranking(db, club_id, page=3, size=2)
    assert [item.position for item in first.items] == [1, 2]
    assert [item.position for item in second.items] == [3, 4]
    assert [item.position for item in last.items] == [5]
    assert all(result.total_pages == 3 for result in (first, second, last))
    assert all(result.user_club_ranking.position == 4 for result in (first, second, last))


def test_service_single_club_and_exact_page(db, club):
    result = get_club_ranking(db, club.id, size=1)
    assert result.total_pages == 1
    assert result.total_clubs == 1
    assert result.items[0].position == 1
    assert result.items[0].avatar is None
    assert result.user_club_ranking.ranking_points == 0
    assert get_club_ranking(db, club.id, page=2, size=1).items == []


def test_service_default_page_with_requester_on_next_page(db, club):
    for index in range(20):
        user = User(
            username=f"ranked-{index}",
            email=f"ranked-{index}@test.com",
            password_hash="test",
        )
        user.club = Club(name=f"Club {index:02d}", ranking_points=20 - index)
        db.add(user)
    db.commit()

    first = get_club_ranking(db, club.id)
    second = get_club_ranking(db, club.id, page=2)

    assert (first.page, first.size, first.total_pages, first.total_clubs) == (1, 20, 2, 21)
    assert [item.position for item in first.items] == list(range(1, 21))
    assert [item.ranking_points for item in first.items] == list(range(20, 0, -1))
    assert club.id not in [item.club_id for item in first.items]
    assert first.user_club_ranking.position == 21
    assert first.user_club_ranking.ranking_points == 0
    assert [(item.club_id, item.position) for item in second.items] == [(club.id, 21)]
    assert second.user_club_ranking == first.user_club_ranking


def test_http_contract(client, auth_headers, ranked_clubs):
    response = client.get("/api/clubs/ranking?page=1&size=2", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "position": position,
                "clubId": ranked_clubs[name].id,
                "clubName": name,
                "avatar": f"{name}.png",
                "rankingPoints": 50,
            }
            for position, name in [(1, "Alpha"), (2, "Zulu")]
        ],
        "page": 1,
        "size": 2,
        "totalPages": 3,
        "totalClubs": 5,
        "userClubRanking": {"position": 4, "rankingPoints": 28},
    }


def test_http_defaults_and_out_of_range(client, auth_headers, ranked_clubs):
    response = client.get("/api/clubs/ranking", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 20
    assert len(body["items"]) == 5
    response = client.get("/api/clubs/ranking?page=4&size=2", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 4,
        "size": 2,
        "totalPages": 3,
        "totalClubs": 5,
        "userClubRanking": {"position": 4, "rankingPoints": 28},
    }


@pytest.mark.parametrize(
    "query", ["page=0", "page=-1", "size=0", "size=-1", "page=abc", "size=1.5"]
)
def test_invalid_pagination(client, auth_headers, query):
    assert client.get(f"/api/clubs/ranking?{query}", headers=auth_headers).status_code == 422


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-token", "Basic invalid"])
def test_requires_valid_jwt(client, authorization):
    headers = {"Authorization": authorization} if authorization else {}
    response = client.get("/api/clubs/ranking", headers=headers)
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("invalid_session", ["expired_token", "revoked", "expired_session"])
def test_rejects_expired_or_revoked_auth(client, db, club, auth_headers, invalid_session):
    session = db.scalar(select(AuthSession).where(AuthSession.user_id == club.user_id))
    if invalid_session == "expired_token":
        token = create_access_token(
            club.user_id, session.id, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        auth_headers = {"Authorization": f"Bearer {token}"}
    elif invalid_session == "revoked":
        session.revoked = True
    else:
        session.expires_at = 0
    db.commit()
    assert client.get("/api/clubs/ranking", headers=auth_headers).status_code == 401
