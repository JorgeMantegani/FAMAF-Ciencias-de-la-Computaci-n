from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.match import ESTADO_FINISHED, ESTADO_SCHEDULED, Match
from app.models.player import Player
from app.models.room import (
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_PRIVATE,
    ROOM_TYPE_PUBLIC,
    Room,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.models.user import User
from app.services.exceptions_league import (
    DuplicateLeagueName,
    InvalidLeaguePassword,
    MaxClubsBelowMin,
    MaxClubsTooHigh,
    MinClubsTooLow,
    PasswordNotAllowedOnPublicLeague,
)
from app.services.league_service import (
    MAX_LEAGUE_PASSWORD_BYTES,
    MIN_LEAGUE_PASSWORD_LENGTH,
)


def league_payload(club_players, behavior, **changes) -> dict:
    """Arma un payload válido de creación de liga; `changes` pisa campos puntuales."""
    payload = {
        "name": "Test League",
        "min_clubs": 3,
        "max_clubs": 4,
        "match_duration": 90,
        "starters": [
            {"player_id": club_players[i].id, "behavior_id": str(behavior.id)} for i in range(3)
        ],
        "substitutes": [
            {"player_id": club_players[i].id, "behavior_id": str(behavior.id)}
            for i in range(3, 6)
        ],
    }
    payload.update(changes)
    return payload


def assert_invalid_squad(response) -> None:
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_SQUAD"


# Caso feliz: devuelve 201 y deja guardados Room, Enrollment y 6 SquadEntry.
def test_create_league(
    client: TestClient,
    db: Session,
    club: Club,
    comportamiento_prueba: Behavior,
    club_players: list[Player],
    auth_headers,
):
    payload = league_payload(club_players, comportamiento_prueba)
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 201
    assert response.json()["name"] == "Test League"
    assert response.json()["is_private"] is False
    assert response.json()["has_penalty_shootout"] is False
    assert response.json()["creator_id"] == club.id

    room = db.scalars(select(Room)).one()
    assert room.creator_club_id == club.id
    assert room.status == ROOM_STATUS_WAITING_GUEST
    assert room.password_hash is None
    assert room.has_penalty_shootout is False

    # Enrollment
    enrollments = db.scalars(select(Enrollment)).all()
    assert len(enrollments) == 1
    assert enrollments[0].club_id == club.id

    # SquadEntry
    squad_entries = db.scalars(select(SquadEntry)).all()
    assert len(squad_entries) == 6
    assert sum(entry.role == ROLE_STARTER for entry in squad_entries) == 3
    assert sum(entry.role == ROLE_SUBSTITUTE for entry in squad_entries) == 3
    assert {e.player_id for e in squad_entries} == {p.id for p in club_players}


def test_create_league_with_penalty_shootout(
    client, db, club, club_players, comportamiento_prueba, auth_headers
):
    payload = league_payload(
        club_players,
        comportamiento_prueba,
        has_penalty_shootout=True,
    )

    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 201
    assert response.json()["has_penalty_shootout"] is True
    room = db.scalars(select(Room)).one()
    assert room.has_penalty_shootout is True


def test_league_standings_score_regular_wins_penalties_and_draws(
    client, db, club, other_club, auth_headers
):
    third_user = User(
        username="third",
        email="third@other.com",
        password_hash="hash",
    )
    third_user.club = Club(name="Third Club")
    db.add(third_user)
    db.flush()
    third_club = third_user.club

    league = Room(
        name="Standings League",
        type=ROOM_TYPE_PUBLIC,
        creator_club_id=club.id,
        min_clubs=3,
        max_clubs=4,
        match_duration_minutes=90,
        has_penalty_shootout=True,
    )
    db.add(league)
    db.flush()
    db.add_all(
        Enrollment(room_id=league.id, club_id=club_id)
        for club_id in (club.id, other_club.id, third_club.id)
    )
    db.add_all(
        [
            Match(
                room_id=league.id,
                home_club_id=club.id,
                away_club_id=other_club.id,
                status=ESTADO_FINISHED,
                home_goals=2,
                away_goals=1,
                duration_seconds=5400,
            ),
            Match(
                room_id=league.id,
                home_club_id=other_club.id,
                away_club_id=third_club.id,
                status=ESTADO_FINISHED,
                home_goals=1,
                away_goals=1,
                penalty_winner_club_id=other_club.id,
                duration_seconds=5400,
            ),
            Match(
                room_id=league.id,
                home_club_id=club.id,
                away_club_id=third_club.id,
                status=ESTADO_FINISHED,
                home_goals=0,
                away_goals=0,
                duration_seconds=5400,
            ),
            Match(
                room_id=league.id,
                home_club_id=third_club.id,
                away_club_id=other_club.id,
                status=ESTADO_SCHEDULED,
                duration_seconds=5400,
            ),
        ]
    )
    db.commit()

    response = client.get(
        f"/api/leagues/{league.id}/standings", headers=auth_headers
    )

    assert response.status_code == 200
    standings = {row["club_id"]: row for row in response.json()}
    assert standings[club.id]["points"] == 4
    assert standings[club.id]["matches_won"] == 1
    assert standings[club.id]["matches_drawn"] == 1
    assert standings[club.id]["matches_played"] == 2
    assert standings[other_club.id]["points"] == 2
    assert standings[other_club.id]["matches_won"] == 1
    assert standings[other_club.id]["matches_lost"] == 1
    assert standings[other_club.id]["matches_played"] == 2
    assert standings[third_club.id]["points"] == 1
    assert standings[third_club.id]["matches_drawn"] == 1
    assert standings[third_club.id]["matches_lost"] == 1
    assert standings[third_club.id]["matches_played"] == 2


# min_clubs por debajo del mínimo permitido: 400 y no se guarda nada.
def test_create_league_min_clubs_too_low(
    client, db, club_players, comportamiento_prueba, auth_headers
):
    payload = league_payload(club_players, comportamiento_prueba, min_clubs=2)
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == MinClubsTooLow(2).message
    assert db.scalars(select(Room)).all() == []


# max_clubs por encima del máximo permitido: 400 y no se guarda nada.
def test_create_league_max_clubs_too_high(
    client, db, club_players, comportamiento_prueba, auth_headers
):
    payload = league_payload(club_players, comportamiento_prueba, max_clubs=31)
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == MaxClubsTooHigh(31).message
    assert db.scalars(select(Room)).all() == []


# max_clubs menor que min_clubs (ambos válidos por separado): 400.
def test_create_league_max_below_min(client, db, club_players, comportamiento_prueba, auth_headers):
    payload = league_payload(club_players, comportamiento_prueba, min_clubs=5)
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == MaxClubsBelowMin(max_clubs=4, min_clubs=5).message
    assert db.scalars(select(Room)).all() == []


# El mismo jugador dos veces entre los titulares: 400.
def test_create_league_duplicate_player(
    client, db, club_players, comportamiento_prueba, auth_headers
):
    repeated = club_players[0]
    behavior_id = str(comportamiento_prueba.id)

    payload = league_payload(
        club_players,
        comportamiento_prueba,
        starters=[
            {"player_id": repeated.id, "behavior_id": behavior_id},
            {"player_id": repeated.id, "behavior_id": behavior_id},
            {"player_id": club_players[1].id, "behavior_id": behavior_id},
        ],
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert_invalid_squad(response)
    assert db.scalars(select(Room)).all() == []


# Un jugador de otro club: 400.
def test_create_league_player_only_in_other_club(
    client, db, club_players, comportamiento_prueba, crear_player, other_club, auth_headers
):
    foreign = crear_player(other_club.id, name="Foreign")
    behavior_id = str(comportamiento_prueba.id)

    payload = league_payload(
        club_players,
        comportamiento_prueba,
        starters=[
            {"player_id": foreign.id, "behavior_id": behavior_id},
            {"player_id": club_players[0].id, "behavior_id": behavior_id},
            {"player_id": club_players[1].id, "behavior_id": behavior_id},
        ],
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert_invalid_squad(response)
    assert db.scalars(select(Room)).all() == []


# No se puede usar un comportamiento de otro club: 400.
def test_create_league_behavior_of_other_club(
    client, db, club_players, comportamiento_prueba, other_club, auth_headers
):
    foreign_behavior = Behavior(
        club_id=other_club.id, name="Foreign", code="def comportamiento(jugador):\n    pass\n"
    )
    db.add(foreign_behavior)
    db.commit()

    payload = league_payload(club_players, foreign_behavior)
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert_invalid_squad(response)
    assert db.scalars(select(Room)).all() == []


# Un comportamiento que no existe en la BD: 400.
def test_create_league_unknown_behavior(
    client, db, club_players, comportamiento_prueba, auth_headers
):
    unknown = str(uuid4())
    valid = str(comportamiento_prueba.id)

    payload = league_payload(
        club_players,
        comportamiento_prueba,
        starters=[
            {"player_id": club_players[0].id, "behavior_id": valid},
            {"player_id": club_players[1].id, "behavior_id": valid},
            {"player_id": club_players[2].id, "behavior_id": unknown},
        ],
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert_invalid_squad(response)
    assert db.scalars(select(Room)).all() == []


# Dos ligas con el mismo nombre: la segunda da 400 y queda una sola Room.
def test_create_league_duplicate_name(
    client, db, club_players, comportamiento_prueba, auth_headers
):
    payload = league_payload(club_players, comportamiento_prueba)

    first = client.post("/api/leagues", headers=auth_headers, json=payload)
    assert first.status_code == 201

    second = client.post("/api/leagues", headers=auth_headers, json=payload)
    assert second.status_code == 400
    assert second.json()["detail"] == DuplicateLeagueName("Test League").message
    assert len(db.scalars(select(Room)).all()) == 1


# Sin token: 401, el endpoint corta antes de llegar al service.
def test_create_league_without_token(client, club_players, comportamiento_prueba):
    payload = league_payload(club_players, comportamiento_prueba)
    response = client.post("/api/leagues", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Sesión inválida o vencida"


# Liga privada válida: 201, tipo privado y contraseña guardada solo como hash.
def test_create_private_league(client, db, club_players, comportamiento_prueba, auth_headers):
    password = "secret1"
    payload = league_payload(
        club_players, comportamiento_prueba, is_private=True, password=password
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 201
    assert response.json()["is_private"] is True
    assert "password" not in response.json()

    room = db.scalars(select(Room)).one()
    assert room.type == ROOM_TYPE_PRIVATE
    assert room.password_hash != password
    assert verify_password(password, room.password_hash)


# Contraseñas inválidas en una liga privada: cada caso da 400 con su motivo.
@pytest.mark.parametrize(
    ("password", "reason"),
    [
        (None, "a password is required for private leagues"),
        ("", "a password is required for private leagues"),
        (
            "a" * (MIN_LEAGUE_PASSWORD_LENGTH - 1),
            f"it must have at least {MIN_LEAGUE_PASSWORD_LENGTH} characters",
        ),
        ("abc def1", "it cannot contain spaces"),
        (
            "a" * (MAX_LEAGUE_PASSWORD_BYTES + 1),
            f"it cannot exceed {MAX_LEAGUE_PASSWORD_BYTES} bytes",
        ),
    ],
)
def test_create_private_league_invalid_password(
    client, db, club_players, comportamiento_prueba, auth_headers, password, reason
):
    payload = league_payload(
        club_players, comportamiento_prueba, is_private=True, password=password
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == InvalidLeaguePassword(reason).message
    assert db.scalars(select(Room)).all() == []


# Una liga pública no puede traer contraseña: 400.
def test_create_public_league_with_password(
    client, db, club_players, comportamiento_prueba, auth_headers
):
    payload = league_payload(
        club_players, comportamiento_prueba, is_private=False, password="secret1"
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == PasswordNotAllowedOnPublicLeague().message
    assert db.scalars(select(Room)).all() == []


# Una liga pública con contraseña vacía se acepta como pública.
def test_create_public_league_with_empty_password(
    client, db, club_players, comportamiento_prueba, auth_headers
):
    payload = league_payload(club_players, comportamiento_prueba, is_private=False, password="")
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 201
    assert response.json()["is_private"] is False
    assert db.scalars(select(Room)).one().password_hash is None
