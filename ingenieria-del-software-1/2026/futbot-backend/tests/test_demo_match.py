from sqlalchemy import func, select

from app.models.goal import Goal
from app.models.match import Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import Room
from app.models.user import User
from scripts.demo_match import PASSWORD, advance_demo, create_demo


def test_demo_login_and_both_users_see_updates(client, db):
    demo = create_demo(db)
    headers = []
    for email in demo.emails:
        login = client.post('/api/auth/login', json={'email': email, 'password': PASSWORD})
        assert login.status_code == 200
        headers.append({'Authorization': f"Bearer {login.json()['access_token']}"})
    path = f'/matches/{demo.match_id}/state'
    initial = client.get(path, headers=headers[0])
    assert initial.status_code == 200
    assert initial.json() == client.get(path, headers=headers[1]).json()
    assert len(initial.json()['players']) == 12
    assert sum(p['on_field'] for p in initial.json()['players']) == 6
    lineup = db.scalars(select(MatchPlayer).where(MatchPlayer.match_id == demo.match_id)).all()
    for player in initial.json()['players']:
        entry = next(mp for mp in lineup if mp.player_id == player['player_id'])
        if player['on_field']:
            assert player['position'] == {'x': entry.initial_x, 'y': entry.initial_y}
        else:
            assert player['position'] is None
    revision = 1
    for elapsed, score in [(40, {'home': 1, 'away': 0}), (80, {'home': 1, 'away': 1}), (120, {'home': 1, 'away': 1})]:
        revision = advance_demo(db, demo, elapsed, revision)
        state = client.get(path, headers=headers[0]).json()
        assert state == client.get(path, headers=headers[1]).json()
        assert state['score'] == score
        assert state['revision'] == revision
        assert state['current_time'] == elapsed
        if elapsed < 120:
            assert state['actions'][0]['type'] == 'goal'
            assert state['players'] != initial.json()['players']
    goals = list(db.scalars(select(Goal).where(Goal.match_id == demo.match_id).order_by(Goal.second)))
    assert len(goals) == 2
    assert [goal.second for goal in goals] == [40, 80]
    assert [goal.club_id for goal in goals] == demo.club_ids
    assert state['status'] == 'finished'
    assert db.get(Room, demo.room_id).status == 'finished'
    assert all(not db.get(Player, pid).is_playing for squad in demo.player_ids for pid in squad)
    assert client.get(path).status_code == 401


def test_new_run_preserves_previous_data(db, login_user):
    first = create_demo(db)
    second = create_demo(db)
    assert first.match_id != second.match_id
    assert set(first.emails).isdisjoint(second.emails)
    assert db.get(User, login_user.id).email == login_user.email
    assert db.scalar(select(func.count()).select_from(Match)) == 2
    assert db.get(Match, first.match_id).status == 'in_progress'
