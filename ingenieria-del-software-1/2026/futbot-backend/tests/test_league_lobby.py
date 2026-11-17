from fastapi import status
from sqlalchemy import select

from app.models.enrollment import Enrollment
from app.models.room import (
    Room,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_TYPE_PUBLIC,
)
from app.models.squad_entry import (
    SquadEntry,
    ROLE_STARTER,
    ROLE_SUBSTITUTE,
)

# Funcion auxiliar para crear una liga activa con un club y jugadores asociados
def create_active_league(db, club, club_players, comportamiento_prueba):
    room = Room(
        type=ROOM_TYPE_PUBLIC,
        name="Liga de prueba",
        creator_club_id=club.id,
        min_clubs=3,
        max_clubs=3,
        match_duration_minutes=5,
        status=ROOM_STATUS_IN_PROGRESS,
    )
    db.add(room)
    db.flush()

    db.add(Enrollment(room_id=room.id, club_id=club.id))

    db.add_all(
        [
            SquadEntry(
                room_id=room.id,
                player_id=player.id,
                behavior_id=comportamiento_prueba.id,
                role=ROLE_STARTER if index < 3 else ROLE_SUBSTITUTE,
            )
            for index, player in enumerate(club_players)
        ]
    )

    db.commit()
    return room


def test_update_lineup_successfully(client, db, auth_headers, club, club_players, comportamiento_prueba):
    league = create_active_league(db, club, club_players, comportamiento_prueba)
    payload = {
        "starters": [player.id for player in club_players[3:6]],
        "substitutes": [player.id for player in club_players[0:3]],
    }
    response = client.put(
        f"/api/leagues/{league.id}/lineup",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "message": "Alineación actualizada correctamente",
        "effectiveNextMatch": True,
        "starters": payload["starters"],
        "substitutes": payload["substitutes"],
    }

    entries = db.scalars(
        select(SquadEntry).where(SquadEntry.room_id == league.id)
    ).all()

    roles = {entry.player_id: entry.role for entry in entries}

    for player_id in payload["starters"]:
        assert roles[player_id] == ROLE_STARTER

    for player_id in payload["substitutes"]:
        assert roles[player_id] == ROLE_SUBSTITUTE

def test_update_lineup_rejects_duplicate_players(client, db, auth_headers, club, club_players, comportamiento_prueba):
    league = create_active_league(db, club, club_players, comportamiento_prueba)
    payload = {
        "starters": [
            club_players[0].id,
            club_players[1].id,
            club_players[2].id,
        ],
        "substitutes": [
            club_players[0].id,
            club_players[4].id,
            club_players[5].id,
        ],
    }

    response = client.put(
        f"/api/leagues/{league.id}/lineup",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "no pueden repetirse" in response.json()["detail"]

def test_update_lineup_rejects_player_from_another_club(client, db, auth_headers, club, club_players, other_club_players, comportamiento_prueba):
    league = create_active_league(db, club, club_players, comportamiento_prueba)

    payload = {
        "starters": [
            club_players[0].id,
            club_players[1].id,
            other_club_players[0].id,
        ],
        "substitutes": [
            club_players[3].id,
            club_players[4].id,
            club_players[5].id,
        ],
    }

    response = client.put(
        f"/api/leagues/{league.id}/lineup",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "no pertenecen al club" in response.json()["detail"]

def test_update_lineup_rejects_invalid_lengths(client, auth_headers, match_en_pre_match, club_players):
    payload = {
        "starters": [player.id for player in club_players[:4]],
        "substitutes": [player.id for player in club_players[4:6]],
    }

    response = client.put(
        f"/api/leagues/{match_en_pre_match.id}/lineup",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY