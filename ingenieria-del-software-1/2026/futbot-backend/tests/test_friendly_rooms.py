from collections.abc import Callable

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club
from app.db.base import ahora_utc as utc_now
from app.main import app
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.match import ESTADO_FINISHED as MATCH_FINISHED
from app.models.match import ESTADO_IN_PROGRESS as MATCH_IN_PROGRESS
from app.models.match import Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import (
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_FRIENDLY,
    ROOM_TYPE_PUBLIC,
    Room,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.models.user import User
from app.services.auth import start_session
from app.services.friendly_rooms import (
    is_behavior_in_active_match,
    start_friendly_match,
)

"""Tests for the friendly room endpoints."""

MATCH_DURATION_MINUTES = 5


# --- Data helpers ---


def create_club(db: Session, name: str) -> Club:
    user = User(username=name, email=f"{name}@futbot.test", password_hash="hash")
    db.add(user)
    db.flush()
    club = Club(user_id=user.id, name=name)
    db.add(club)
    db.commit()
    return club


def create_behavior(db: Session, club_id: str | None, name: str) -> Behavior:
    behavior = Behavior(
        club_id=club_id,
        name=name,
        code="def comportamiento(jugador):\n    pass\n",
        is_preprogrammed=club_id is None,
    )
    db.add(behavior)
    db.commit()
    return behavior


def add_squad(
    db: Session, room: Room, club: Club, behavior: Behavior, create_player
) -> list[Player]:
    db.add(Enrollment(room_id=room.id, club_id=club.id))
    players = [create_player(club.id) for _ in range(6)]
    for index, player in enumerate(players):
        db.add(
            SquadEntry(
                room_id=room.id,
                player_id=player.id,
                behavior_id=behavior.id,
                role=ROLE_STARTER if index < 3 else ROLE_SUBSTITUTE,
            )
        )
    db.commit()
    return players


def create_friendly_room(db: Session, creator: Club, room_status: str) -> Room:
    room = Room(
        type=ROOM_TYPE_FRIENDLY,
        creator_club_id=creator.id,
        min_clubs=2,
        max_clubs=2,
        match_duration_minutes=MATCH_DURATION_MINUTES,
        status=room_status,
    )
    db.add(room)
    db.commit()
    return room


def start_url(room_id: str) -> str:
    return f"/api/friendly/rooms/{room_id}/start"


# --- Fixtures ---


@pytest.fixture(autouse=True)
def isolated_motor_behaviors(monkeypatch):
    # Estos tests usan una DB temporal; no consultar el catálogo global de bots.
    from app.engine.match_engine import MatchEngine

    async def actions(self):
        from app.engine.action import NULL_ACTION
        return {player.id: NULL_ACTION for player in self.state.players}

    monkeypatch.setattr(MatchEngine, '_collect_actions', actions)


@pytest.fixture
def away_club(db: Session) -> Club:
    return create_club(db, "away")


@pytest.fixture
def default_behavior(db: Session) -> Behavior:
    return create_behavior(db, None, "correr")


@pytest.fixture
def ready_room(
    db: Session, club: Club, away_club: Club, default_behavior: Behavior, crear_player
) -> Room:
    room = create_friendly_room(db, club, ROOM_STATUS_READY_TO_START)
    add_squad(db, room, club, default_behavior, crear_player)
    add_squad(db, room, away_club, default_behavior, crear_player)
    return room


@pytest.fixture
def login_as(client: TestClient) -> Callable[[Club], None]:
    """Authenticates as the given club (overrides the auth placeholder)."""

    def _login(club: Club) -> None:
        app.dependency_overrides[get_current_club] = lambda: club

    return _login


def assert_error(response, status_code: int, error_code: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert body["error_code"] == error_code
    assert isinstance(body["detail"], str)


def count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --- Success ---


def test_start_returns_ok_and_the_match_id(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    login_as(club)

    response = client.post(start_url(ready_room.id))

    assert response.status_code == 200
    match = db.scalars(select(Match)).one()
    assert response.json() == {
        "roomId": ready_room.id,
        "matchId": match.id,
        "status": "inProgress",
    }


def test_start_moves_room_and_match_to_in_progress(
    client: TestClient,
    login_as,
    club: Club,
    away_club: Club,
    ready_room: Room,
    db: Session,
) -> None:
    login_as(club)

    client.post(start_url(ready_room.id))

    db.refresh(ready_room)
    assert ready_room.status == ROOM_STATUS_IN_PROGRESS
    assert ready_room.started_at is not None

    match = db.scalars(select(Match)).one()
    assert match.status == MATCH_IN_PROGRESS
    assert match.home_club_id == club.id
    assert match.away_club_id == away_club.id
    assert match.duration_seconds == MATCH_DURATION_MINUTES * 60
    assert match.started_at is not None


def test_start_creates_the_lineup_and_locks_the_players(
    client: TestClient,
    login_as,
    club: Club,
    ready_room: Room,
    default_behavior: Behavior,
    db: Session,
) -> None:
    login_as(club)

    client.post(start_url(ready_room.id))

    match_players = db.scalars(select(MatchPlayer)).all()
    assert len(match_players) == 12
    assert sum(mp.on_field for mp in match_players) == 6
    assert all(mp.behavior_id == default_behavior.id for mp in match_players)

    players = db.scalars(select(Player)).all()
    for player in players:
        db.refresh(player)
    assert all(player.is_playing for player in players)


def test_the_away_club_can_also_start(
    client: TestClient, login_as, away_club: Club, ready_room: Room
) -> None:
    login_as(away_club)

    assert client.post(start_url(ready_room.id)).status_code == 200


# --- Auth and access ---


def test_start_without_authentication_is_rejected(
    client: TestClient, ready_room: Room, db: Session
) -> None:
    response = client.post(start_url(ready_room.id))

    assert_error(response, 401, "UNAUTHORIZED")
    assert response.headers["www-authenticate"] == "Bearer"
    assert count(db, Match) == 0


def bearer(db: Session, club: Club) -> dict[str, str]:
    """Authorization header of a real login session."""
    return {"Authorization": f"Bearer {start_session(db, club.user).access_token}"}


def test_start_with_a_valid_session(
    client: TestClient, club: Club, ready_room: Room, db: Session
) -> None:
    response = client.post(start_url(ready_room.id), headers=bearer(db, club))

    assert response.status_code == 200


@pytest.mark.parametrize("authorization", ["Bearer not-a-jwt", "Basic dXNlcjpwYXNz"])
def test_start_with_an_invalid_token_is_rejected(
    client: TestClient, ready_room: Room, db: Session, authorization: str
) -> None:
    response = client.post(
        start_url(ready_room.id), headers={"Authorization": authorization}
    )

    assert_error(response, 401, "UNAUTHORIZED")
    assert count(db, Match) == 0


def test_start_after_logout_is_rejected(
    client: TestClient, club: Club, ready_room: Room, db: Session
) -> None:
    headers = bearer(db, club)
    client.post("/api/auth/logout", headers=headers)

    assert_error(client.post(start_url(ready_room.id), headers=headers), 401, "UNAUTHORIZED")
    assert count(db, Match) == 0


def test_unknown_room_is_not_found(
    client: TestClient, login_as, club: Club
) -> None:
    login_as(club)

    assert_error(client.post(start_url("room-that-does-not-exist")), 404, "ROOM_NOT_FOUND")


def test_a_league_room_is_not_found(
    client: TestClient, login_as, club: Club, db: Session
) -> None:
    league = Room(
        type=ROOM_TYPE_PUBLIC,
        name="League",
        creator_club_id=club.id,
        min_clubs=3,
        max_clubs=4,
        match_duration_minutes=MATCH_DURATION_MINUTES,
        status=ROOM_STATUS_READY_TO_START,
    )
    db.add(league)
    db.flush()  # generates league.id
    db.add(Enrollment(room_id=league.id, club_id=club.id))
    db.commit()
    login_as(club)

    assert_error(client.post(start_url(league.id)), 404, "ROOM_NOT_FOUND")


def test_a_club_outside_the_room_is_forbidden(
    client: TestClient, login_as, ready_room: Room, db: Session
) -> None:
    login_as(create_club(db, "outsider"))

    assert_error(client.post(start_url(ready_room.id)), 403, "NOT_ROOM_MEMBER")
    assert count(db, Match) == 0


# --- Room state ---


def test_a_match_cannot_be_started_twice(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    login_as(club)
    client.post(start_url(ready_room.id))

    response = client.post(start_url(ready_room.id))

    assert_error(response, 400, "MATCH_ALREADY_STARTED")
    assert count(db, Match) == 1


def test_a_room_without_guest_is_not_full(
    client: TestClient,
    login_as,
    club: Club,
    default_behavior: Behavior,
    db: Session,
    crear_player,
) -> None:
    room = create_friendly_room(db, club, ROOM_STATUS_WAITING_GUEST)
    add_squad(db, room, club, default_behavior, crear_player)
    login_as(club)

    assert_error(client.post(start_url(room.id)), 400, "ROOM_NOT_FULL")


def test_a_cancelled_room_is_not_ready(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    ready_room.status = ROOM_STATUS_CANCELLED
    db.commit()
    login_as(club)

    assert_error(client.post(start_url(ready_room.id)), 400, "ROOM_NOT_READY")


def test_a_concurrent_start_is_detected(
    engine: Engine, club: Club, ready_room: Room, db: Session
) -> None:
    """The other club starts the room after this request read it."""
    db.get(Room, ready_room.id)
    with engine.begin() as other_request:
        other_request.execute(
            update(Room)
            .where(Room.id == ready_room.id)
            .values(status=ROOM_STATUS_IN_PROGRESS, started_at=utc_now())
        )

    with pytest.raises(HTTPException) as error:
        start_friendly_match(db, ready_room.id, club)

    assert error.value.status_code == 400
    assert error.value.detail["error_code"] == "MATCH_ALREADY_STARTED"
    assert count(db, Match) == 0


# --- Squads ---


def assert_invalid_squad_without_side_effects(
    client: TestClient, room: Room, db: Session
) -> None:
    assert_error(client.post(start_url(room.id)), 400, "INVALID_SQUAD")
    db.refresh(room)
    assert room.status == ROOM_STATUS_READY_TO_START
    assert count(db, Match) == 0
    assert count(db, MatchPlayer) == 0


def test_a_squad_with_only_two_starters_is_invalid(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    starter = db.scalars(
        select(SquadEntry)
        .join(Player, SquadEntry.player_id == Player.id)
        .where(Player.club_id == club.id, SquadEntry.role == ROLE_STARTER)
    ).first()
    db.delete(starter)
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


def test_a_squad_with_a_deleted_player_is_invalid(
    client: TestClient, login_as, club: Club, away_club: Club, ready_room: Room, db: Session
) -> None:
    player = db.scalars(select(Player).where(Player.club_id == away_club.id)).first()
    player.deleted_at = utc_now()
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


def test_a_squad_with_a_player_from_a_third_club_is_invalid(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session, crear_player
) -> None:
    entry = db.scalars(
        select(SquadEntry)
        .join(Player, SquadEntry.player_id == Player.id)
        .where(Player.club_id == club.id)
    ).first()
    entry.player_id = crear_player(create_club(db, "third").id).id
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


def test_a_squad_with_a_player_already_playing_is_invalid(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    player = db.scalars(select(Player).where(Player.club_id == club.id)).first()
    player.is_playing = True
    db.commit()
    login_as(club)

    assert_error(client.post(start_url(ready_room.id)), 400, "INVALID_SQUAD")


def test_a_squad_with_another_clubs_behavior_is_invalid(
    client: TestClient, login_as, club: Club, away_club: Club, ready_room: Room, db: Session
) -> None:
    foreign_behavior = create_behavior(db, club.id, "home_only")
    entry = db.scalars(
        select(SquadEntry)
        .join(Player, SquadEntry.player_id == Player.id)
        .where(Player.club_id == away_club.id)
    ).first()
    entry.behavior_id = foreign_behavior.id
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


def test_a_squad_with_a_deleted_behavior_is_invalid(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    own_behavior = create_behavior(db, club.id, "deleted")
    own_behavior.deleted_at = utc_now()
    entry = db.scalars(
        select(SquadEntry)
        .join(Player, SquadEntry.player_id == Player.id)
        .where(Player.club_id == club.id)
    ).first()
    entry.behavior_id = own_behavior.id
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


# --- Behavior lock ---


def test_behaviors_are_locked_only_while_the_match_is_active(
    client: TestClient,
    login_as,
    club: Club,
    ready_room: Room,
    default_behavior: Behavior,
    db: Session,
) -> None:
    unused_behavior = create_behavior(db, club.id, "unused")
    assert not is_behavior_in_active_match(db, default_behavior.id)

    login_as(club)
    client.post(start_url(ready_room.id))

    assert is_behavior_in_active_match(db, default_behavior.id)
    assert not is_behavior_in_active_match(db, unused_behavior.id)

    db.execute(update(Match).values(status=MATCH_FINISHED))
    db.commit()
    assert not is_behavior_in_active_match(db, default_behavior.id)


# --- GET /api/friendly/rooms/{room_id} ---


def room_url(room_id: str) -> str:
    return f"/api/friendly/rooms/{room_id}"


def test_read_a_ready_room(
    client: TestClient,
    login_as,
    club: Club,
    away_club: Club,
    ready_room: Room,
    default_behavior: Behavior,
) -> None:
    login_as(club)

    response = client.get(room_url(ready_room.id))

    assert response.status_code == 200
    body = response.json()
    assert body["roomId"] == ready_room.id
    assert body["status"] == "readyToStart"
    assert body["matchId"] is None
    assert body["homeClub"]["clubId"] == club.id
    assert body["homeClub"]["clubName"] == club.name
    assert body["awayClub"]["clubId"] == away_club.id

    players = body["homeClub"]["players"]
    assert [p["role"] for p in players] == [ROLE_STARTER] * 3 + [ROLE_SUBSTITUTE] * 3
    assert players[0]["behaviorId"] == default_behavior.id
    assert players[0]["behaviorName"] == default_behavior.name


def test_read_a_room_without_guest(
    client: TestClient,
    login_as,
    club: Club,
    default_behavior: Behavior,
    db: Session,
    crear_player,
) -> None:
    room = create_friendly_room(db, club, ROOM_STATUS_WAITING_GUEST)
    add_squad(db, room, club, default_behavior, crear_player)
    login_as(club)

    body = client.get(room_url(room.id)).json()

    assert body["status"] == "waitingGuest"
    assert body["awayClub"] is None
    assert len(body["homeClub"]["players"]) == 6


def test_read_a_started_room_includes_the_match(
    client: TestClient, login_as, away_club: Club, ready_room: Room
) -> None:
    login_as(away_club)
    match_id = client.post(start_url(ready_room.id)).json()["matchId"]

    body = client.get(room_url(ready_room.id)).json()

    assert body["status"] == "inProgress"
    assert body["matchId"] == match_id


def test_read_a_room_requires_authentication(
    client: TestClient, ready_room: Room
) -> None:
    assert_error(client.get(room_url(ready_room.id)), 401, "UNAUTHORIZED")


def test_read_an_unknown_room_is_not_found(
    client: TestClient, login_as, club: Club
) -> None:
    login_as(club)

    assert_error(client.get(room_url("room-that-does-not-exist")), 404, "ROOM_NOT_FOUND")


def test_read_a_room_of_another_club_is_forbidden(
    client: TestClient, login_as, ready_room: Room, db: Session
) -> None:
    login_as(create_club(db, "outsider"))

    assert_error(client.get(room_url(ready_room.id)), 403, "NOT_ROOM_MEMBER")


# --- POST /api/friendly/rooms ---


def test_create_friendly_room_unauthorized_without_token(client: TestClient):
    """
    Debe rechazar la peticion con 401 Unauthorized si no se envia el token.
    """
    response = client.post("/api/friendly/rooms", json={})
    assert response.status_code == 401
    assert response.json()["detail"] == "Sesión inválida o vencida"

def test_create_friendly_room_unauthorized_invalid_token(client: TestClient):
    """
    Debe rechazar la peticion con 401 Unauthorized si el token es invalido.
    """
    headers = {"Authorization": "Bearer token.jwt.invalido"}
    response = client.post("/api/friendly/rooms", headers=headers, json={})
    assert response.status_code == 401
    assert response.json()["detail"] == "Sesión inválida o vencida"

def test_create_friendly_room_integration_success(
        client: TestClient,
        db: Session,
        club,
        auth_headers: dict[str, str],
        crear_player,
        comportamiento_prueba,
):
    """
    Prueba el flujo punta a punta (HTTP -> Auth -> Service -> DB).
    """
    # Crear 6 jugadores para el club usando fixture
    jugadores = [crear_player(club.id, name=f"Jugador {i}") for i in range(1,7)]

    # Formatear payload con titulares y suplentes
    payload = {
        "starters": [
            {"player_id": p.name, "behavior_id": str(comportamiento_prueba.id)}
            for p in jugadores[:3]
        ],
        "substitutes": [
            {"player_id": p.name, "behavior_id": str(comportamiento_prueba.id)}
            for p in jugadores[3:]
        ],
    }

    # Peticion HTTP autenticada
    response = client.post("/api/friendly/rooms", headers=auth_headers, json=payload)

    # asserciones de la respuesta http
    assert response.status_code == 201
    data = response.json()
    assert "room_id" in data
    assert "room_code" in data
    assert data["status"] == "waitingGuest"
    assert data["home_club"] == str(club.id)

    # verificacion de persistencia
    created_room = db.get(Room, data["room_id"])
    assert created_room is not None
    assert created_room.type == ROOM_TYPE_FRIENDLY
    assert created_room.status == ROOM_STATUS_WAITING_GUEST
    assert created_room.creator_club_id == club.id

    # verificacion de alineaciones
    squad_entries = db.query(SquadEntry).filter_by(room_id=data["room_id"]).all()
    assert len(squad_entries) == 6
    starters = [s for s in squad_entries if s.role == ROLE_STARTER]
    substitutes = [s for s in squad_entries if s.role == ROLE_SUBSTITUTE]
    assert len(starters) == 3
    assert len(substitutes) == 3

def test_create_friendly_room_validation_pydantic_int_input(
    client: TestClient, auth_headers: dict[str, str]
):
    """
    Pydantic debe rechazar entradas numéricas (422 Unprocessable Entity).
    """
    payload = {
        "starters": [
            {"player_id": 1, "behavior_id": "b-1"},  # int en vez de str
            {"player_id": "p-2", "behavior_id": "b-1"},
            {"player_id": "p-3", "behavior_id": "b-1"},
        ],
        "substitutes": [
            {"player_id": "p-4", "behavior_id": "b-1"},
            {"player_id": "p-5", "behavior_id": "b-1"},
            {"player_id": "p-6", "behavior_id": "b-1"},
        ],
    }

    response = client.post("/api/friendly/rooms", headers=auth_headers, json=payload)
    assert response.status_code == 422

def test_create_friendly_room_duplicate_players_400(
    client: TestClient,
    club,
    auth_headers: dict[str, str],
    crear_player,
    comportamiento_prueba,
):
    """
    El servicio debe retornar 400 Bad Request si hay jugadores repetidos.
    """
    p1 = crear_player(club.id, name="Jugador 1")
    p2 = crear_player(club.id, name="Jugador 2")

    payload = {
        "starters": [
            {"player_id": str(p1.id), "behavior_id": str(comportamiento_prueba.id)},
            {"player_id": str(p1.id), "behavior_id": str(comportamiento_prueba.id)},  # Repetido
            {"player_id": str(p2.id), "behavior_id": str(comportamiento_prueba.id)},
        ],
        "substitutes": [
            {"player_id": str(p2.id), "behavior_id": str(comportamiento_prueba.id)},
            {"player_id": str(p2.id), "behavior_id": str(comportamiento_prueba.id)},
            {"player_id": str(p2.id), "behavior_id": str(comportamiento_prueba.id)},
        ],
    }

    response = client.post("/api/friendly/rooms", headers=auth_headers, json=payload)
    assert response.status_code == 400
    assert "mismo jugador" in response.json()["detail"].lower()

def test_start_publishes_initial_state_for_websocket(client, db, club, ready_room, auth_headers):
    response = client.post(start_url(ready_room.id), headers=auth_headers)
    assert response.status_code == 200
    match_id = response.json()['matchId']
    with client.websocket_connect(f'/api/matches/{match_id}/ws') as socket:
        socket.send_json({'type': 'auth', 'token': auth_headers['Authorization'].split()[1]})
        message = socket.receive_json()
    assert message['type'] == 'state'
    state = message['state']
    assert state['match_id'] == match_id
    assert state['revision'] >= 1
    assert len(state['players']) == 12
    assert sum(p['on_field'] for p in state['players']) == 6
    assert state['ball']['x'] == 0
    assert state['ball']['y'] == 0


def test_runner_publishes_ticks_and_finishes_once(db, club, ready_room, monkeypatch):
    import asyncio
    from app.core.config import get_settings
    from app.engine.live_state import match_states
    from app.engine.match_engine import MatchEngine
    from app.engine.schedule import build_schedule
    from app.engine.state import GoalEvent, Team
    from app.models.goal import Goal
    from app.services import match_runner
    from app.ws.manager import manager

    match = start_friendly_match(db, ready_room.id, club)
    match.duration_seconds = 4
    db.commit()
    original_build = match_runner.build_engine_from_db
    seen = []
    monkeypatch.setattr(manager, 'broadcast', lambda state: seen.append(state))

    async def actions(self):
        # Un gol en el primer tick permite verificar que no se persista de nuevo al finalizar.
        if not self.state.goals:
            scorer = next(p for p in self.state.players if p.team == Team.HOME)
            self.state.goals.append(GoalEvent(Team.HOME, scorer.id, 0))
            self.state.score[Team.HOME] = 1
        from app.engine.action import NULL_ACTION
        return {player.id: NULL_ACTION for player in self.state.players}

    monkeypatch.setattr(MatchEngine, '_collect_actions', actions)

    def fast_engine(*args, **kwargs):
        engine = original_build(*args, **kwargs)
        engine.schedule = build_schedule(4, engine.cfg.match_tick_rate, 0, 0)
        engine.realtime = False
        return engine

    monkeypatch.setattr(match_runner, 'build_engine_from_db', fast_engine)

    async def play():
        match_runner.start_match(db, match.id, get_settings())
        initial = match_states.get(match.id)
        assert initial.revision == 1
        assert initial.current_time == 0
        with pytest.raises(RuntimeError):
            match_runner.start_match(db, match.id, get_settings())
        await match_runner._running[match.id]
        await asyncio.sleep(0)
        assert match.id not in match_runner._running

    asyncio.run(play())
    final = match_states.get(match.id)
    assert final.status == 'finished'
    assert final.current_time == 4
    assert final.score.home == 1
    assert len(seen) > 2
    assert [s.revision for s in seen] == list(range(1, len(seen) + 1))
    db.expire_all()
    assert db.get(Match, match.id).status == MATCH_FINISHED
    assert db.get(Room, ready_room.id).status == 'finished'
    assert db.scalar(select(func.count()).select_from(Goal).where(Goal.match_id == match.id)) == 1
    assert all(not db.get(Player, str(p.player_id)).is_playing for p in final.players)


def test_retry_start_requires_membership_and_recovers_unstarted_match(
    client, db, club, away_club, ready_room, auth_headers,
):
    from app.engine.live_state import match_states

    match = start_friendly_match(db, ready_room.id, club)
    url = f'/matches/{match.id}/start'
    assert client.post(url).status_code == 401
    outsider = create_club(db, 'retry-outsider')
    outsider_session = start_session(db, outsider.user)
    assert client.post(url, headers={
        'Authorization': f'Bearer {outsider_session.access_token}',
    }).status_code == 403
    assert match_states.get(match.id) is None
    assert client.post(url, headers=auth_headers).status_code == 202
    assert match_states.get(match.id) is not None
    assert client.post(url, headers=auth_headers).status_code == 409
