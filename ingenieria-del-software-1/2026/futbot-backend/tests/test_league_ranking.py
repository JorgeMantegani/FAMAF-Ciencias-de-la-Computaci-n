"""El cierre real de una liga acredita el ranking una sola vez."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.init_db import crear_tablas
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.match import (
    ESTADO_FINISHED,
    ESTADO_IN_PROGRESS,
    ESTADO_PAUSED,
    ESTADO_PRE_MATCH,
    ESTADO_SCHEDULED,
    Match,
)
from app.models.room import (
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_TYPE_FRIENDLY,
    ROOM_TYPE_PRIVATE,
    ROOM_TYPE_PUBLIC,
    Room,
)
from app.models.user import User
from app.services import league_orchestrator
from app.services.club_ranking import get_club_ranking
from app.services.league_ranking import (
    recover_finished_league_rankings,
    settle_league_ranking,
)


@pytest.fixture
def completed_league(db, club, other_club):
    third = User(username="third", email="third@test.com", password_hash="test")
    third.club = Club(name="Third", ranking_points=30)
    db.add(third)
    club.ranking_points = 10
    other_club.ranking_points = 20
    db.flush()
    clubs = [club, other_club, third.club]
    room = Room(
        name="Ranking league", type=ROOM_TYPE_PUBLIC, creator_club_id=club.id,
        min_clubs=3, max_clubs=3, match_duration_minutes=5,
        status=ROOM_STATUS_IN_PROGRESS,
    )
    db.add(room)
    db.flush()
    for participant in clubs:
        # No confiar en acumulados que un callback duplicado podría haber alterado.
        db.add(Enrollment(room_id=room.id, club_id=participant.id, points=99))
    for home, away, goals in [(0, 1, (2, 0)), (1, 2, (1, 1)), (2, 0, (1, 0))]:
        db.add(Match(
            room_id=room.id, home_club_id=clubs[home].id, away_club_id=clubs[away].id,
            home_goals=goals[0], away_goals=goals[1], status=ESTADO_FINISHED,
            duration_seconds=300,
        ))
    db.commit()
    return room.id, [participant.id for participant in clubs]


def points(db, club_ids):
    db.expire_all()
    return [db.get(Club, club_id).ranking_points for club_id in club_ids]


def test_public_league_awards_results_and_preserves_existing_points(db, completed_league):
    league_id, club_ids = completed_league
    assert settle_league_ranking(db, league_id)
    db.commit()
    assert points(db, club_ids) == [13, 21, 34]
    assert db.get(Room, league_id).status == ROOM_STATUS_FINISHED
    assert db.get(Room, league_id).ranking_settled
    ranking = get_club_ranking(db, club_ids[0])
    assert [item.ranking_points for item in ranking.items] == [34, 21, 13]
    assert ranking.user_club_ranking.ranking_points == 13
    assert ranking.user_club_ranking.position == 3


def test_repeated_closure_in_another_session_does_not_award_twice(db, completed_league):
    league_id, club_ids = completed_league
    assert settle_league_ranking(db, league_id)
    db.commit()
    with Session(db.get_bind()) as retry:
        assert not settle_league_ranking(retry, league_id)
        retry.commit()
    assert points(db, club_ids) == [13, 21, 34]


def test_rollback_keeps_closure_and_points_atomic(db, completed_league):
    league_id, club_ids = completed_league
    assert settle_league_ranking(db, league_id)
    db.rollback()
    assert points(db, club_ids) == [10, 20, 30]
    assert db.get(Room, league_id).status == ROOM_STATUS_IN_PROGRESS
    assert not db.get(Room, league_id).ranking_settled
    assert settle_league_ranking(db, league_id)
    db.commit()
    assert points(db, club_ids) == [13, 21, 34]


def test_concurrent_closures_award_only_once(db, engine, completed_league):
    league_id, club_ids = completed_league
    barrier = Barrier(2)

    def close():
        with Session(engine) as worker:
            barrier.wait(timeout=10)
            claimed = settle_league_ranking(worker, league_id)
            worker.commit()
            return claimed

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = [pool.submit(close) for _ in range(2)]
        assert sorted(attempt.result(timeout=15) for attempt in attempts) == [False, True]
    assert points(db, club_ids) == [13, 21, 34]


def test_empty_fixture_is_not_closed(db, completed_league):
    league_id, club_ids = completed_league
    for match in db.scalars(select(Match).where(Match.room_id == league_id)):
        db.delete(match)
    db.commit()
    assert not settle_league_ranking(db, league_id)
    assert points(db, club_ids) == [10, 20, 30]
    assert db.get(Room, league_id).status == ROOM_STATUS_IN_PROGRESS


@pytest.mark.parametrize("status", [
    ESTADO_SCHEDULED, ESTADO_PRE_MATCH, ESTADO_IN_PROGRESS, ESTADO_PAUSED,
])
def test_does_not_close_with_unfinished_matches(db, completed_league, status):
    league_id, club_ids = completed_league
    match = db.scalar(select(Match).where(Match.room_id == league_id))
    match.status = status
    db.commit()
    assert not settle_league_ranking(db, league_id)
    db.commit()
    assert points(db, club_ids) == [10, 20, 30]
    assert db.get(Room, league_id).status == ROOM_STATUS_IN_PROGRESS


@pytest.mark.parametrize("kind", [ROOM_TYPE_PRIVATE, ROOM_TYPE_FRIENDLY])
def test_private_leagues_and_friendlies_do_not_award_points(db, completed_league, kind):
    league_id, club_ids = completed_league
    room = db.get(Room, league_id)
    room.type = kind
    if kind == ROOM_TYPE_PRIVATE:
        room.password_hash = "hash"
    else:
        room.min_clubs = room.max_clubs = 2
    db.commit()
    assert settle_league_ranking(db, league_id) == (kind == ROOM_TYPE_PRIVATE)
    db.commit()
    assert points(db, club_ids) == [10, 20, 30]


def test_cancelled_league_is_not_awarded(db, completed_league):
    league_id, club_ids = completed_league
    db.get(Room, league_id).status = ROOM_STATUS_CANCELLED
    db.commit()
    assert not settle_league_ranking(db, league_id)
    assert points(db, club_ids) == [10, 20, 30]


def test_finished_leagues_recovered_once_after_schema_upgrade(db, engine, completed_league):
    league_id, club_ids = completed_league
    db.get(Room, league_id).status = ROOM_STATUS_FINISHED
    db.commit()
    # Simular una base anterior al cambio, que aún no tenía la marca de acreditación.
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE rooms DROP COLUMN ranking_settled"))
    crear_tablas(engine)
    crear_tablas(engine)
    assert recover_finished_league_rankings(db) == 1
    assert recover_finished_league_rankings(db) == 0
    assert points(db, club_ids) == [13, 21, 34]


@pytest.mark.asyncio
async def test_orchestrator_closes_awards_and_broadcasts(db, completed_league, monkeypatch):
    league_id, club_ids = completed_league
    monkeypatch.setattr(league_orchestrator.asyncio, "sleep", AsyncMock())
    broadcast = AsyncMock()
    monkeypatch.setattr(league_orchestrator.league_manager, "broadcast_active", broadcast)
    await league_orchestrator.run_next_league_match(db.get_bind(), league_id)
    assert points(db, club_ids) == [13, 21, 34]
    assert broadcast.await_args.args[1]["status"] == ROOM_STATUS_FINISHED
    await league_orchestrator.run_next_league_match(db.get_bind(), league_id)
    assert points(db, club_ids) == [13, 21, 34]
    broadcast.assert_awaited_once()
