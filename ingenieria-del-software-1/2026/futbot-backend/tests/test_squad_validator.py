from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.db.base import ahora_utc as utc_now
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.player import Player
from app.schemas.friendly_room import PlayerSelection
from app.services.squad_validator import validate_squad_selection

"""Tests de la validación compartida de plantillas."""


def create_behavior(db: Session, club_id: str | None, name: str = "own") -> Behavior:
    behavior = Behavior(
        club_id=club_id,
        name=name,
        code="def comportamiento(jugador):\n    pass\n",
        is_preprogrammed=club_id is None,
    )
    db.add(behavior)
    db.commit()
    return behavior


def squad(player_ids: list[str], behavior_ids: list[str]) -> tuple[list, list]:
    """Titulares y suplentes a partir de listas paralelas de ids."""
    selections = [
        PlayerSelection(player_id=player_id, behavior_id=behavior_id)
        for player_id, behavior_id in zip(player_ids, behavior_ids)
    ]
    return selections[:3], selections[3:]


def assert_invalid_squad(db: Session, club_id: str, starters, substitutes) -> None:
    with pytest.raises(HTTPException) as error:
        validate_squad_selection(db, club_id, starters, substitutes)
    assert error.value.status_code == 400
    assert error.value.detail["error_code"] == "INVALID_SQUAD"
    assert isinstance(error.value.detail["detail"], str)


@pytest.fixture
def player_ids(club_players: list[Player]) -> list[str]:
    return [player.id for player in club_players]


@pytest.fixture
def default_behavior_id(comportamiento_prueba: Behavior) -> str:
    return comportamiento_prueba.id


# --- Plantillas válidas ---


def test_own_players_with_preprogrammed_and_own_behaviors_are_valid(
    db: Session, club: Club, player_ids: list[str], default_behavior_id: str
) -> None:
    own_behavior_id = create_behavior(db, club.id).id
    # El mismo comportamiento se puede asignar a varios jugadores.
    behavior_ids = [default_behavior_id] * 5 + [own_behavior_id]

    validate_squad_selection(db, club.id, *squad(player_ids, behavior_ids))


# --- Estructura ---


@pytest.mark.parametrize(("starters", "substitutes"), [(2, 3), (3, 2), (4, 2), (0, 0)])
def test_the_squad_needs_three_starters_and_three_substitutes(
    db: Session,
    club: Club,
    player_ids: list[str],
    default_behavior_id: str,
    starters: int,
    substitutes: int,
) -> None:
    selections = [PlayerSelection(player_id=p, behavior_id=default_behavior_id) for p in player_ids]

    assert_invalid_squad(
        db, club.id, selections[:starters], selections[starters:starters + substitutes]
    )


def test_a_repeated_player_is_invalid(
    db: Session, club: Club, player_ids: list[str], default_behavior_id: str
) -> None:
    repeated = player_ids[:5] + player_ids[:1]

    assert_invalid_squad(db, club.id, *squad(repeated, [default_behavior_id] * 6))


# --- Jugadores ---


def test_a_player_of_another_club_is_invalid(
    db: Session,
    club: Club,
    other_club: Club,
    player_ids: list[str],
    default_behavior_id: str,
    crear_player,
) -> None:
    foreign_id = crear_player(other_club.id, name="Foreign").id

    assert_invalid_squad(
        db, club.id, *squad(player_ids[:5] + [foreign_id], [default_behavior_id] * 6)
    )


def test_an_unknown_player_id_is_invalid(
    db: Session, club: Club, player_ids: list[str], default_behavior_id: str
) -> None:
    assert_invalid_squad(
        db, club.id, *squad(player_ids[:5] + [str(uuid4())], [default_behavior_id] * 6)
    )


def test_player_names_are_not_accepted_as_ids(
    db: Session, club: Club, club_players: list[Player], default_behavior_id: str
) -> None:
    names = [player.name for player in club_players]

    assert_invalid_squad(db, club.id, *squad(names, [default_behavior_id] * 6))


def test_a_deleted_player_is_invalid(
    db: Session,
    club: Club,
    club_players: list[Player],
    player_ids: list[str],
    default_behavior_id: str,
) -> None:
    club_players[0].deleted_at = utc_now()
    db.commit()

    assert_invalid_squad(db, club.id, *squad(player_ids, [default_behavior_id] * 6))


# --- Comportamientos ---


def test_a_behavior_of_another_club_is_invalid(
    db: Session, club: Club, other_club: Club, player_ids: list[str], default_behavior_id: str
) -> None:
    foreign_id = create_behavior(db, other_club.id).id

    assert_invalid_squad(
        db, club.id, *squad(player_ids, [default_behavior_id] * 5 + [foreign_id])
    )


def test_an_unknown_behavior_is_invalid(
    db: Session, club: Club, player_ids: list[str], default_behavior_id: str
) -> None:
    assert_invalid_squad(
        db, club.id, *squad(player_ids, [default_behavior_id] * 5 + [str(uuid4())])
    )


def test_a_deleted_behavior_is_invalid(
    db: Session, club: Club, player_ids: list[str], default_behavior_id: str
) -> None:
    deleted = create_behavior(db, club.id)
    deleted.deleted_at = utc_now()
    db.commit()

    assert_invalid_squad(
        db, club.id, *squad(player_ids, [default_behavior_id] * 5 + [deleted.id])
    )


# --- Rendimiento ---


def test_the_whole_squad_is_validated_with_two_queries(
    db: Session, engine: Engine, club: Club, player_ids: list[str], default_behavior_id: str
) -> None:
    starters, substitutes = squad(player_ids, [default_behavior_id] * 6)
    # Leer antes de escuchar: un atributo expirado sumaría una query de refresco.
    club_id = club.id
    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        validate_squad_selection(db, club_id, starters, substitutes)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert len(statements) == 2
