import pytest
from app.engine.field import FieldConfig
from app.engine.setup import (
    PlayerSpec, create_initial_state, reset_to_kickoff,
)
from app.engine.state import MatchPhase, Team, Vec2


def specs(start_id: int) -> list[PlayerSpec]:
    return [PlayerSpec(start_id + i, 60, 60, 60, 60, 60) for i in range(3)] #crea futbolistas con id consecutivos y stats iguales, para pruebas


@pytest.fixture
def field() -> FieldConfig:
    return FieldConfig()


@pytest.fixture
def state(field):
    return create_initial_state(field, specs(1), specs(10))


def test_three_players_per_team(state):
    assert sum(p.team == Team.HOME for p in state.players) == 3
    assert sum(p.team == Team.AWAY for p in state.players) == 3


def test_each_team_starts_in_own_half(state, field):
    half = field.length / 2
    for p in state.players:
        if p.team == Team.HOME:
            assert p.pos.x < half
        else:
            assert p.pos.x > half


def test_players_inside_field(state, field):
    for p in state.players:
        assert 0 <= p.pos.x <= field.length
        assert 0 <= p.pos.y <= field.width


def test_ball_at_center_and_still(state, field):
    assert state.ball.pos == field.center
    assert state.ball.vel == Vec2()
    assert state.ball.owner_id is None


def test_initial_score_and_phase(state):
    assert state.score == {Team.HOME: 0, Team.AWAY: 0}
    assert state.phase == MatchPhase.PRE


def test_reset_to_kickoff_restores_positions(state, field):
    original = [p.pos for p in state.players]
    state.players[0].pos = Vec2(99, 1)
    state.ball.pos = Vec2(5, 5)
    state.ball.vel = Vec2(10, 0)
    state.ball.owner_id = state.players[0].id

    reset_to_kickoff(state, field)

    assert [p.pos for p in state.players] == original
    assert state.ball.pos == field.center
    assert state.ball.vel == Vec2()
    assert state.ball.owner_id is None


def test_wrong_team_size_raises(field):
    with pytest.raises(ValueError):
        create_initial_state(field, specs(1)[:2], specs(10))
        
def test_valid_spec_sums_300():
    PlayerSpec(1, 60, 60, 60, 60, 60)
    PlayerSpec(2, 100, 100, 60, 20, 20)   # extremos válidos


def test_sum_not_300_raises():
    with pytest.raises(ValueError):
        PlayerSpec(1, 50, 50, 50, 50, 50)   # suma 250
    with pytest.raises(ValueError):
        PlayerSpec(1, 70, 70, 70, 70, 70)   # suma 350


@pytest.mark.parametrize("bad", [19, 101]) 
def test_attribute_out_of_range_raises(bad):
    # suma 300 pero un atributo fuera de rango
    rest = (300 - bad) / 4
    with pytest.raises(ValueError):
        PlayerSpec(1, bad, rest, rest, rest, rest)