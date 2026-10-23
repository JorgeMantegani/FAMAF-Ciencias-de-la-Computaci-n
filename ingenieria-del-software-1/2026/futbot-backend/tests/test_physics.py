import pytest

from app.engine.field import FieldConfig
from app.engine.physics import (
    BALL_STOP_SPEED, max_speed_ms, move_player, step_ball, check_goal
)
from app.engine.state import BallState, PlayerState, Team, Vec2

DT = 1 / 15


@pytest.fixture
def field() -> FieldConfig:
    return FieldConfig()


def make_player(pos: Vec2, speed: float = 50) -> PlayerState:
    return PlayerState(
        id=1, team=Team.HOME, pos=pos,
        speed=speed, control=5, strength=5, power=5, agility=5,
    )


# ---------- Jugadores ----------

def test_player_step_limited_by_speed(field):
    p = make_player(Vec2(10, 34), speed=50)
    move_player(p, Vec2(100, 34), DT, field)
    moved = (p.pos - Vec2(10, 34)).length()
    assert moved == pytest.approx(max_speed_ms(50) * DT)


def test_player_does_not_overshoot_target(field):
    p = make_player(Vec2(10, 34))
    move_player(p, Vec2(10.01, 34), DT, field)
    assert p.pos == Vec2(10.01, 34)


def test_faster_player_moves_farther(field):
    slow = make_player(Vec2(10, 34), speed=0)
    fast = make_player(Vec2(10, 34), speed=100)
    move_player(slow, Vec2(100, 34), DT, field)
    move_player(fast, Vec2(100, 34), DT, field)
    assert fast.pos.x > slow.pos.x


def test_player_never_leaves_field(field):
    p = make_player(Vec2(104.9, 67.9), speed=100)
    for _ in range(50):
        move_player(p, Vec2(500, 500), DT, field)
    assert p.pos.x == field.length
    assert p.pos.y == field.width


def test_player_in_place_has_zero_velocity(field):
    p = make_player(Vec2(10, 10))
    move_player(p, Vec2(10, 10), DT, field)
    assert p.vel == Vec2()


# ---------- Pelota ----------

def test_ball_decelerates_each_tick(field):
    ball = BallState(pos=Vec2(20, 34), vel=Vec2(20, 0))
    speeds = []
    for _ in range(30):
        step_ball(ball, DT, field)
        speeds.append(ball.vel.length())
    assert all(a > b for a, b in zip(speeds, speeds[1:]))


def test_ball_eventually_stops(field):
    ball = BallState(pos=Vec2(20, 34), vel=Vec2(5, 0))
    for _ in range(300):
        step_ball(ball, DT, field)
    assert ball.vel == Vec2()


def test_ball_moves_in_velocity_direction(field):
    ball = BallState(pos=Vec2(20, 34), vel=Vec2(10, 0))
    step_ball(ball, DT, field)
    assert ball.pos.x > 20
    assert ball.pos.y == pytest.approx(34)


def test_ball_bounces_on_sideline(field):
    ball = BallState(pos=Vec2(50, 0.1), vel=Vec2(0, -10))
    step_ball(ball, DT, field)
    assert 0 <= ball.pos.y <= field.width
    assert ball.vel.y > 0          # cambió de sentido


def test_ball_bounces_on_goal_line_outside_goal(field):
    ball = BallState(pos=Vec2(104.9, 5), vel=Vec2(10, 0))   # y=5: fuera del arco
    step_ball(ball, DT, field)
    assert ball.pos.x <= field.length
    assert ball.vel.x < 0


def test_ball_passes_through_goal_mouth(field):
    ball = BallState(pos=Vec2(104.9, 34), vel=Vec2(10, 0))  # y=34: dentro del arco
    step_ball(ball, DT, field)
    assert ball.pos.x > field.length
    assert ball.vel.x > 0
    
def test_goal_home_scores_on_right_goal(field):
    assert check_goal(Vec2(104.5, 34), Vec2(105.5, 34), field) == Team.HOME


def test_goal_away_scores_on_left_goal(field):
    assert check_goal(Vec2(0.5, 34), Vec2(-0.5, 34), field) == Team.AWAY


def test_no_goal_when_ball_stays_inside(field):
    assert check_goal(Vec2(50, 34), Vec2(52, 34), field) is None


def test_no_goal_when_crossing_outside_posts(field):
    y_out = field.goal_y_range[1] + 2          # por encima del poste
    assert check_goal(Vec2(104.5, y_out), Vec2(105.5, y_out), field) is None


def test_goal_on_post_line_counts(field):
    y_post = field.goal_y_range[0]
    assert check_goal(Vec2(104.5, y_post), Vec2(105.5, y_post), field) == Team.HOME


def test_fast_shot_does_not_tunnel(field):
    # el remate recorre 10 m en un tick y termina muy lejos de la línea
    assert check_goal(Vec2(100, 34), Vec2(110, 34), field) == Team.HOME


def test_diagonal_shot_uses_crossing_point(field):
    # termina fuera del ancho del arco, pero cruza la línea dentro de él
    assert check_goal(Vec2(104, 30), Vec2(106, 45), field) == Team.HOME  # cruza en y=37.5


def test_ball_leaving_goal_is_not_a_goal(field):
    assert check_goal(Vec2(105.5, 34), Vec2(104.5, 34), field) is None