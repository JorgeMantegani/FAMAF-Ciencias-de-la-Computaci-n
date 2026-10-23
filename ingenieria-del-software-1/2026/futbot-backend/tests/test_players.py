from sqlalchemy import select

from app.core.dependencies import get_current_user
from app.main import app
from app.models.club import Club
from app.models.player import Player
from app.models.user import User

club_dependency = get_current_user


def test_create_player_valid(client, db, club, user):
    app.dependency_overrides[club_dependency] = lambda: user

    response = client.post(
        "/api/players",
        json={
            "name": "New Player",
            "power": 60,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "New Player"

    player = db.scalar(select(Player).where(Player.name == "New Player"))
    assert player is not None
    assert player.club_id == club.id


def test_rejects_attribute_below_20(client, club, user):
    app.dependency_overrides[club_dependency] = lambda: user

    response = client.post(
        "/api/players",
        json={
            "name": "New Player",
            "power": 19,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        },
    )
    assert response.status_code == 400


def test_rejects_attribute_above_100(client, club, user):
    app.dependency_overrides[club_dependency] = lambda: user

    response = client.post(
        "/api/players",
        json={
            "name": "New Player",
            "power": 101,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        },
    )
    assert response.status_code == 400


def test_rejects_sum_different_from_300(client, club, user):
    app.dependency_overrides[club_dependency] = lambda: user

    response = client.post(
        "/api/players",
        json={
            "name": "New Player",
            "power": 50,
            "agility": 50,
            "control": 50,
            "speed": 50,
            "strength": 50,
        },
    )
    assert response.status_code == 400


def test_rejects_name_shorter_than_3(client, club, user):
    app.dependency_overrides[club_dependency] = lambda: user

    response = client.post(
        "/api/players",
        json={
            "name": "AB",
            "power": 60,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        },
    )
    assert response.status_code == 422


def test_rejects_duplicate_name_in_same_club(client, db, club, user):
    app.dependency_overrides[club_dependency] = lambda: user

    db.add(
        Player(
            club_id=club.id,
            name="Duplicate Player",
            power=60,
            agility=60,
            control=60,
            speed=60,
            strength=60,
        )
    )
    db.commit()

    response = client.post(
        "/api/players",
        json={
            "name": "Duplicate Player",
            "power": 60,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        },
    )
    assert response.status_code == 400


def test_name_from_another_club_can_repeat(client, db, club, user):
    app.dependency_overrides[club_dependency] = lambda: user

    other_user = User(
        username="other-tester", email="other@futbot.test", password_hash="test-hash"
    )
    db.add(other_user)
    db.flush()

    other_club = Club(user_id=other_user.id, name="Other Club")
    db.add(other_club)
    db.flush()

    db.add(
        Player(
            club_id=other_club.id,
            name="Common Player",
            power=60,
            agility=60,
            control=60,
            speed=60,
            strength=60,
        )
    )
    db.commit()

    response = client.post(
        "/api/players",
        json={
            "name": "Common Player",
            "power": 60,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        },
    )
    assert response.status_code == 201


# Da FALSED hasta tener integrado el sistema de autenticación.
def test_requires_authentication(client):
    response = client.post(
        "/api/players",
        json={
            "name": "New Player",
            "power": 60,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        },
    )
    assert response.status_code == 401


def test_player_is_linked_to_authenticated_club(client, db, club, user):
    app.dependency_overrides[club_dependency] = lambda: user

    response = client.post(
        "/api/players",
        json={
            "name": "Linked Player",
            "power": 60,
            "agility": 60,
            "control": 60,
            "speed": 60,
            "strength": 60,
        },
    )
    assert response.status_code == 201

    player = db.scalar(select(Player).where(Player.name == "Linked Player"))
    assert player is not None
    assert player.club_id == club.id
