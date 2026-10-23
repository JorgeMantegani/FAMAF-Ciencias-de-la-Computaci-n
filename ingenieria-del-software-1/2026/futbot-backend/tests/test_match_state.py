"""Pruebas de estado con motor simulado y API/base de datos reales (SQLite temporal)."""
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.state import publish_engine_state, publish_engine_tick
from app.engine.live_state import match_states
from app.models.goal import Goal
from app.schemas.match_state import MatchTick
from app.services.match_state import StaleMatchState, publish_match_state


@pytest.fixture
def match_scenario(db):
    from types import SimpleNamespace

    from app.models.behavior import Behavior
    from app.models.club import Club
    from app.models.match import Match
    from app.models.match_player import MatchPlayer
    from app.models.player import Player
    from app.models.room import Room
    from app.models.user import User
    from app.services.auth import start_session

    clubs = {}
    headers = {}
    for role in ("home", "away", "outsider"):
        user = User(username=role, email=f"{role}@futbot.test", password_hash="unused")
        user.club = Club(name=f"Club {role}")
        db.add(user)
        db.flush()
        clubs[role] = user.club
        token = start_session(db, user).access_token
        headers[role] = {"Authorization": f"Bearer {token}"}
    room = Room(type="friendly", creator_club_id=clubs["home"].id,
                min_clubs=2, max_clubs=2, match_duration_minutes=5)
    behavior = Behavior(name="test", code="def comportamiento(jugador): pass",
                        is_preprogrammed=True)
    db.add_all([room, behavior])
    db.flush()
    match = Match(room_id=room.id, home_club_id=clubs["home"].id,
                  away_club_id=clubs["away"].id, status="in_progress", duration_seconds=300)
    db.add(match)
    db.flush()
    players = {}
    for role in ("home", "away"):
        player = Player(club_id=clubs[role].id, name=f"Player {role}",
                        power=60, agility=60, control=60, speed=60, strength=60)
        db.add(player)
        db.flush()
        db.add(MatchPlayer(match_id=match.id, club_id=clubs[role].id,
                           player_id=player.id, behavior_id=behavior.id, on_field=True))
        players[role] = player
    db.commit()
    tick = MatchTick.model_validate({
        "status": "in_progress", "current_time": 0,
        "score": {"home": 0, "away": 0}, "ball": {"x": 5, "y": 3},
        "players": [{"player_id": p.id, "on_field": True, "position": {"x": 0, "y": 0}}
                    for p in players.values()],
    })
    return SimpleNamespace(match=match, headers=headers, tick=tick,
                           home_player=players["home"], away_player=players["away"], **clubs)


@pytest.fixture
def published_match(db, match_scenario, state_engine):
    publish_engine_state(db, match_scenario.match.id, state_engine, expected_revision=0)
    db.commit()
    state_engine.capture_state.assert_called_once_with()
    state_engine.reset_mock()
    return match_scenario


@pytest.fixture
def state_engine(match_scenario):
    from app.schemas.coord import Coord
    from app.schemas.match_state import Position

    class TestEngine:
        """Doble del motor: solo las primitivas usadas por este comportamiento."""
        def __init__(self):
            self.tick = match_scenario.tick.model_copy(deep=True)

        def assigned_behavior(self, player_id):
            return "test"

        def ball_position(self):
            return Coord(x=self.tick.ball.x, y=self.tick.ball.y)

        def is_inside_field(self, position):
            return 0 <= position.x <= 100 and 0 <= position.y <= 60

        def player_is_on_field(self, player_id):
            return any(str(p.player_id) == player_id and p.on_field for p in self.tick.players)

        def apply_movement(self, player_id, destination):
            player = next(p for p in self.tick.players if str(p.player_id) == player_id)
            player.position = Position(x=destination.x, y=destination.y)

        def register_error(self, player_id, message):
            pytest.fail(message)

        def capture_state(self):
            return self.tick.model_copy(deep=True)

    # El doble conserva un estado determinista; el mock permite verificar las
    # llamadas al motor sin reemplazar la publicacion, persistencia ni HTTP.
    fake = TestEngine()
    mocked = Mock(spec_set=fake, wraps=fake)
    mocked.tick = fake.tick
    return mocked


def test_both_participants_read_identical_state_without_writes(client, db, published_match, state_engine):
    scenario = published_match
    path = f"/matches/{scenario.match.id}/state"
    before = match_states.get(scenario.match.id).model_dump(mode="json")
    for participant in ("home", "away", "home"):
        response = client.get(path, headers=scenario.headers[participant])
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == before
    assert before["home_club"] == {"club_id": scenario.home.id, "name": scenario.home.name}
    assert before["away_club"]["club_id"] == scenario.away.id
    assert before["score"] == {"home": 0, "away": 0}
    assert before["remaining_time"] == 300
    assert len(before["players"]) == 2
    assert match_states.get(scenario.match.id).model_dump(mode="json") == before
    assert not db.new and not db.dirty and not db.deleted
    assert state_engine.mock_calls == []


@pytest.mark.parametrize("participant,status", [(None, 401), ("outsider", 403)])
def test_access_denied(client, published_match, participant, status):
    headers = published_match.headers.get(participant, {})
    response = client.get(f"/matches/{published_match.match.id}/state", headers=headers)
    assert response.status_code == status
    assert "players" not in response.json()


def test_unknown_match_returns_404(client, match_scenario):
    response = client.get(f"/matches/{uuid4()}/state", headers=match_scenario.headers["home"])
    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_missing_state_does_not_initialize_match(client, db, match_scenario):
    path = f"/matches/{match_scenario.match.id}/state"
    response = client.get(path, headers=match_scenario.headers["home"])
    assert response.status_code == 409
    assert match_states.get(match_scenario.match.id) is None
    # La autorizacion se verifica antes de informar que no hay estado.
    assert client.get(path, headers=match_scenario.headers["outsider"]).status_code == 403


def test_next_tick_updates_complete_snapshot_and_persisted_score(client, db, published_match):
    scenario = published_match
    data = scenario.tick.model_dump(mode="json")
    data.update(current_time=42, score={"home": 1, "away": 0})
    data["players"][0]["position"] = {"x": 12, "y": 3}
    data["ball"].update(x=12, y=3, owner_player_id=scenario.home_player.id)
    data["actions"] = [{"type": "goal", "player_id": scenario.home_player.id, "club_id": scenario.home.id}]
    publish_engine_tick(db, scenario.match.id, MatchTick.model_validate(data), expected_revision=1)
    response = client.get(f"/matches/{scenario.match.id}/state", headers=scenario.headers["away"])
    state = response.json()
    assert state["revision"] == 2
    assert state["score"] == {"home": 1, "away": 0}
    assert state["result"] == "1-0"
    assert state["current_time"] == 42 and state["remaining_time"] == 258
    assert state["actions"][0]["type"] == "goal"
    player = next(p for p in state["players"] if p["player_id"] == scenario.home_player.id)
    assert player["position"] == {"x": 12, "y": 3} and player["has_ball"]
    db.refresh(scenario.match)
    assert scenario.match.home_goals == 1


def test_stale_tick_cannot_overwrite_newer_revision(db, published_match):
    scenario = published_match
    publish_match_state(db, scenario.match.id, scenario.tick, expected_revision=1)
    db.commit()
    before = match_states.get(scenario.match.id).model_dump(mode="json")
    with pytest.raises(StaleMatchState):
        publish_match_state(db, scenario.match.id, scenario.tick, expected_revision=1)
    assert match_states.get(scenario.match.id).model_dump(mode="json") == before


def test_movement_tick_has_no_sql_writes_or_commit(db, engine, published_match):
    from sqlalchemy import event
    scenario = published_match
    writes, commits = [], []
    def record_sql(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE', 'REPLACE'):
            writes.append(statement)
    def committed(session):
        commits.append(True)
    event.listen(engine, 'before_cursor_execute', record_sql)
    event.listen(db, 'after_commit', committed)
    try:
        tick = scenario.tick.model_copy(deep=True)
        tick.current_time = 1
        state = publish_engine_tick(db, scenario.match.id, tick, expected_revision=1)
        assert state.revision == 2
        assert writes == [] and commits == []
        assert not db.new and not db.dirty
        db.rollback()  # No hay transacción de persistencia para un tick en vivo.
        assert match_states.get(scenario.match.id).revision == 2
    finally:
        event.remove(engine, 'before_cursor_execute', record_sql)
        event.remove(db, 'after_commit', committed)


def test_state_is_shared_between_sessions_in_the_same_process(engine, published_match):
    from app.services.match_state import get_match_state
    from app.models.user import User
    with Session(engine) as reader:
        user = reader.get(User, published_match.home.user_id)
        state = get_match_state(reader, published_match.match.id, user)
        assert str(state.match_id) == published_match.match.id
        assert state.revision == 1
        state.score.home = 100
        assert match_states.get(published_match.match.id).score.home == 0


@pytest.mark.parametrize("change", ["duplicate", "foreign_player", "missing_player", "invalid_owner", "too_late", "foreign_action"])
def test_invalid_tick_does_not_change_published_state(db, published_match, change):
    scenario = published_match
    data = scenario.tick.model_dump(mode="json")
    if change == "duplicate":
        data["players"].append(data["players"][0])
    elif change == "foreign_player":
        data["players"][0]["player_id"] = str(uuid4())
    elif change == "missing_player":
        data["players"].pop()
    elif change == "invalid_owner":
        data["ball"]["owner_player_id"] = str(uuid4())
    elif change == "too_late":
        data["current_time"] = 301
    else:
        data["actions"] = [{"type": "goal", "club_id": scenario.outsider.id}]
    with pytest.raises(ValueError):
        publish_match_state(db, scenario.match.id, MatchTick.model_validate(data), expected_revision=1)
    assert match_states.get(scenario.match.id).revision == 1


def test_paused_and_finished_states_and_no_reopening(db, published_match):
    scenario = published_match
    data = scenario.tick.model_dump()
    data.update(status="paused", current_time=100)
    publish_match_state(db, scenario.match.id, MatchTick.model_validate(data), expected_revision=1)
    db.commit()
    data.update(status="finished", current_time=300)
    final = publish_match_state(db, scenario.match.id, MatchTick.model_validate(data), expected_revision=2)
    db.commit()
    assert final.remaining_time == 0 and final.status == "finished"
    with pytest.raises(ValueError, match="termino"):
        publish_match_state(db, scenario.match.id, scenario.tick, expected_revision=3)


def test_rejects_non_finite_coordinates():
    with pytest.raises(ValidationError):
        MatchTick.model_validate({"status": "in_progress", "current_time": 0,
            "score": {"home": 0, "away": 0}, "ball": {"x": float("nan"), "y": 0}, "players": []})


def test_get_is_only_public_operation(client, published_match):
    path = f"/matches/{published_match.match.id}/state"
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(path, headers=published_match.headers["home"]).status_code == 405


def test_concurrent_publishers_cannot_overwrite_each_other(engine, published_match):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)
    match_id = published_match.match.id
    tick = published_match.tick

    def publish():
        with Session(engine) as writer:
            barrier.wait(timeout=10)
            try:
                state = publish_match_state(writer, match_id, tick, expected_revision=1)
                writer.commit()
                return state.revision
            except StaleMatchState:
                writer.rollback()
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    assert results.count(2) == 1
    assert results.count(None) == 1
    with Session(engine) as reader:
        assert match_states.get(match_id).revision == 2


def test_behavior_updates_state_with_mocked_engine(client, db, published_match, state_engine, monkeypatch):
    from app.behaviors import loader
    from app.behaviors.executor import ejecutar_comportamiento
    from app.schemas.coord import Coord
    from app.schemas.match_state import Position

    def behavior(player):
        player.correr(player.encontrar_pelota())

    monkeypatch.setattr(loader, "_cache", {"test": behavior})
    scenario = published_match
    ejecutar_comportamiento(scenario.home_player.id, state_engine)
    state = publish_engine_state(db, scenario.match.id, state_engine, expected_revision=1)
    db.commit()
    player = next(p for p in state.players if str(p.player_id) == scenario.home_player.id)
    assert player.position == Position(x=5, y=3)
    assert state.revision == 2
    state_engine.apply_movement.assert_called_once_with(scenario.home_player.id, Coord(x=5, y=3))
    state_engine.capture_state.assert_called_once_with()
    state_engine.register_error.assert_not_called()
    for participant in ("home", "away"):
        response = client.get(f"/matches/{scenario.match.id}/state", headers=scenario.headers[participant])
        assert response.status_code == 200
        assert response.json() == state.model_dump(mode="json")


def test_mocked_engine_publishes_match_lifecycle(client, db, match_scenario, state_engine):
    """Simula inicio, gol, pausa, reanudacion y fin sin un loop de simulacion."""
    scenario = match_scenario
    initial = scenario.tick.model_dump(mode="json")
    goal = scenario.tick.model_dump(mode="json")
    goal.update(current_time=42, score={"home": 1, "away": 0})
    goal["actions"] = [{"type": "goal", "player_id": scenario.home_player.id,
                        "club_id": scenario.home.id}]
    snapshots = [
        initial,
        goal,
        {**goal, "status": "paused", "actions": [{"type": "pause"}]},
        {**goal, "actions": [{"type": "resume"}]},
        {**goal, "status": "finished", "current_time": 300, "actions": []},
    ]
    ticks = [MatchTick.model_validate(snapshot) for snapshot in snapshots]
    state_engine.capture_state.side_effect = ticks

    for revision, tick in enumerate(ticks, start=1):
        publish_engine_state(db, scenario.match.id, state_engine, expected_revision=revision - 1)
        db.commit()
        states = []
        for participant in ("home", "away"):
            response = client.get(f"/matches/{scenario.match.id}/state", headers=scenario.headers[participant])
            assert response.status_code == 200
            states.append(response.json())
        assert states[0] == states[1]
        state = states[0]
        assert state["revision"] == revision
        assert state["status"] == tick.status
        assert state["score"] == tick.score.model_dump()
        assert state["current_time"] == tick.current_time
        assert state["remaining_time"] == 300 - tick.current_time
        assert state["actions"] == [action.model_dump(mode="json") for action in tick.actions]
        db.refresh(scenario.match)
        assert scenario.match.status == tick.status
        assert scenario.match.home_goals == tick.score.home
        assert scenario.match.away_goals == tick.score.away

    assert state_engine.capture_state.call_count == len(ticks)


def test_invalid_match_id_returns_422(client, match_scenario):
    response = client.get('/matches/not-a-uuid/state', headers=match_scenario.headers['home'])
    assert response.status_code == 422


def test_failed_goal_commit_does_not_publish_or_leave_a_goal(db, published_match, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    scenario = published_match
    tick = scenario.tick.model_copy(deep=True)
    tick.score.home = 1
    from app.schemas.match_state import MatchAction
    tick.actions = [MatchAction(
        type='goal', club_id=scenario.home.id, player_id=scenario.home_player.id)]
    def fail():
        raise SQLAlchemyError('Disco no disponible')
    monkeypatch.setattr(db, 'commit', fail)
    with pytest.raises(SQLAlchemyError):
        publish_engine_tick(db, scenario.match.id, tick, expected_revision=1)
    assert match_states.get(scenario.match.id).revision == 1
    assert list(db.scalars(select(Goal))) == []
    db.refresh(scenario.match)
    assert scenario.match.home_goals == 0


def test_goal_is_saved_once_and_replayed_revision_is_rejected(db, published_match):
    from app.schemas.match_state import MatchAction
    scenario = published_match
    tick = scenario.tick.model_copy(deep=True)
    tick.current_time = 42
    tick.score.home = 1
    tick.actions = [MatchAction(type='goal', club_id=scenario.home.id, player_id=scenario.home_player.id)]
    publish_engine_tick(db, scenario.match.id, tick, expected_revision=1)
    with pytest.raises(StaleMatchState):
        publish_engine_tick(db, scenario.match.id, tick, expected_revision=1)
    goals = list(db.scalars(select(Goal)))
    assert len(goals) == 1
    assert goals[0].player_id == scenario.home_player.id
    assert goals[0].club_id == scenario.home.id
    assert goals[0].second == 42
    tick.current_time = 43
    tick.actions = []
    publish_engine_tick(db, scenario.match.id, tick, expected_revision=2)
    assert len(list(db.scalars(select(Goal)))) == 1


def test_score_without_a_goal_event_is_rejected_by_engine(db, published_match):
    scenario = published_match
    tick = scenario.tick.model_copy(deep=True)
    tick.score.home = 1
    with pytest.raises(ValueError, match='evento de gol'):
        publish_engine_tick(db, scenario.match.id, tick, expected_revision=1)
    assert match_states.get(scenario.match.id).revision == 1
