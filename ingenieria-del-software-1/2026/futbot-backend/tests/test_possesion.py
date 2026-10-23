import random

import pytest

from app.engine.action import Kick
from app.engine.physics import (
    CONTROL_RADIUS, KICK_COOLDOWN_TICKS, KICK_MAX_SPEED, KICK_MIN_SPEED,
    PASS_DIST_FACTOR, PASS_SPEED_FACTOR, apply_kick, resolve_possession,
)
from app.engine.state import BallState, PlayerState, Team, Vec2


def make(pid, pos, team=Team.HOME, control=60, strength=60, power=60):
    return PlayerState(id=pid, team=team, pos=pos, speed=60, control=control,
                       strength=strength, power=power, agility=60)


# ---------- Remates ----------

def test_kick_without_ball_does_nothing():
    ball = BallState(pos=Vec2(50, 34), owner_id="a0")
    p = make("h0", Vec2(50, 34))
    assert apply_kick(ball, p, Kick("shot", Vec2(105, 34))) is False
    assert ball.vel == Vec2()


def test_shot_speed_depends_on_power():
    for power, expected in ((20, KICK_MIN_SPEED), (100, KICK_MAX_SPEED)):
        ball = BallState(pos=Vec2(50, 34), owner_id="h0")
        p = make("h0", Vec2(50, 34), power=power)
        apply_kick(ball, p, Kick("shot", Vec2(105, 34)))
        assert ball.vel.length() == pytest.approx(expected)


def test_shot_goes_toward_target():
    ball = BallState(pos=Vec2(50, 34), owner_id="h0")
    apply_kick(ball, make("h0", Vec2(50, 34)), Kick("shot", Vec2(50, 60)))
    assert ball.vel.x == pytest.approx(0)
    assert ball.vel.y > 0


def test_short_pass_is_gentler_than_shot():
    ball = BallState(pos=Vec2(50, 34), owner_id="h0")
    p = make("h0", Vec2(50, 34), power=100)
    apply_kick(ball, p, Kick("pass", Vec2(55, 34)))            # 5 m
    assert ball.vel.length() == pytest.approx(5 * PASS_DIST_FACTOR)
    assert ball.vel.length() < KICK_MAX_SPEED


def test_long_pass_capped_by_power():
    ball = BallState(pos=Vec2(10, 34), owner_id="h0")
    p = make("h0", Vec2(10, 34), power=100)
    apply_kick(ball, p, Kick("pass", Vec2(100, 34)))
    assert ball.vel.length() == pytest.approx(KICK_MAX_SPEED * PASS_SPEED_FACTOR)


def test_kick_releases_ball_and_starts_cooldown():
    ball = BallState(pos=Vec2(50, 34), owner_id="h0")
    apply_kick(ball, make("h0", Vec2(50, 34)), Kick("shot", Vec2(105, 34)))
    assert ball.owner_id is None
    assert ball.last_kicker_id == "h0"
    assert ball.cooldown_ticks == KICK_COOLDOWN_TICKS


# ---------- Posesión ----------

def test_nearby_player_takes_free_ball():
    ball = BallState(pos=Vec2(50, 34))
    p = make("h0", Vec2(50.5, 34))
    resolve_possession(ball, [p], random.Random(0))
    assert ball.owner_id == "h0"
    assert ball.pos == p.pos


def test_far_player_does_not_take_ball():
    ball = BallState(pos=Vec2(50, 34))
    p = make("h0", Vec2(50 + CONTROL_RADIUS + 0.5, 34))
    resolve_possession(ball, [p], random.Random(0))
    assert ball.owner_id is None


def test_ball_follows_its_owner():
    ball = BallState(pos=Vec2(50, 34), owner_id="h0")
    p = make("h0", Vec2(60, 30))
    resolve_possession(ball, [p], random.Random(0))
    assert ball.owner_id == "h0"
    assert ball.pos == Vec2(60, 30)
    assert ball.vel == Vec2()


def test_kicker_cannot_retake_during_cooldown():
    ball = BallState(pos=Vec2(50, 34), last_kicker_id="h0", cooldown_ticks=3)
    kicker = make("h0", Vec2(50, 34))
    resolve_possession(ball, [kicker], random.Random(0))
    assert ball.owner_id is None


def test_kicker_can_retake_after_cooldown():
    ball = BallState(pos=Vec2(50, 34), last_kicker_id="h0", cooldown_ticks=0)
    resolve_possession(ball, [make("h0", Vec2(50, 34))], random.Random(0))
    assert ball.owner_id == "h0"


def test_rival_can_intercept_during_cooldown():
    ball = BallState(pos=Vec2(50, 34), last_kicker_id="h0", cooldown_ticks=3)
    kicker = make("h0", Vec2(50, 34))
    rival = make("a0", Vec2(50.5, 34), team=Team.AWAY)
    resolve_possession(ball, [kicker, rival], random.Random(0))
    assert ball.owner_id == "a0"


def test_cooldown_counts_down():
    ball = BallState(pos=Vec2(50, 34), cooldown_ticks=3)
    resolve_possession(ball, [], random.Random(0))
    assert ball.cooldown_ticks == 2


def test_fast_free_ball_cannot_be_controlled():
    ball = BallState(pos=Vec2(50, 34), vel=Vec2(30, 0))
    resolve_possession(ball, [make("h0", Vec2(50, 34))], random.Random(0))
    assert ball.owner_id is None


def test_stronger_player_wins_more_disputes():
    rng = random.Random(42)
    wins = 0
    for _ in range(1000):
        ball = BallState(pos=Vec2(50, 34))
        strong = make("h0", Vec2(50, 34), control=100, strength=100)
        weak = make("a0", Vec2(50.2, 34), team=Team.AWAY, control=20, strength=20)
        resolve_possession(ball, [strong, weak], rng)
        wins += ball.owner_id == "h0"
    assert wins > 600      # probabilidad esperada ~75 %