import pytest
from app.schemas.coord import Coord
from app.core.config import settings
from app.engine.primitives import MatchEngine, PlayerState, PLAYER_MAX_SPEED, BALL_MAX_POWER


@pytest.fixture
def match_setup():
    """Estado estático del juego con PlayerState y PACSS reales."""
    players_data = {
        "p1": PlayerState(
            club_id="CLUB_A",
            position=Coord(x=0.0, y=0.0),
            own_goal=Coord(x=-50.0, y=0.0),
            enemy_goal=Coord(x=50.0, y=0.0),
            speed=100,  # Avanza ~0.6 por tick
            power=100,  # Balón avanza ~1.67 por tick
            control=100,
            is_on_field=True,
            behavior_id="beh_01",
        ),
        "aliado_1": PlayerState(
            club_id="CLUB_A",
            position=Coord(x=5.0, y=0.0),
            own_goal=Coord(x=-50.0, y=0.0),
            enemy_goal=Coord(x=50.0, y=0.0),
            speed=60,
            power=60,
            control=60,
            is_on_field=True,
            behavior_id="beh_02",
        ),
        "enemigo_1": PlayerState(
            club_id="CLUB_B",
            position=Coord(x=10.0, y=0.0),
            own_goal=Coord(x=50.0, y=0.0),
            enemy_goal=Coord(x=-50.0, y=0.0),
            speed=60,
            power=60,
            control=60,
            is_on_field=True,
            behavior_id="beh_03",
        ),
    }
    ball_pos = Coord(x=0.5, y=0.0)  # Cerca de p1 (dentro de su radio de control)
    engine = MatchEngine(players_data, ball_pos)
    return engine


def test_consultas_posiciones_y_arcos(match_setup):
    engine = match_setup
    assert engine.ball_position() == Coord(x=0.5, y=0.0)
    assert engine.player_position("p1") == Coord(x=0.0, y=0.0)
    assert engine.own_goal_position("p1") == Coord(x=-50.0, y=0.0)
    assert engine.opponent_goal_position("p1") == Coord(x=50.0, y=0.0)


def test_busqueda_aliados_y_enemigos(match_setup):
    engine = match_setup
    assert engine.nearest_teammate_position("p1") == Coord(x=5.0, y=0.0)
    assert engine.nearest_opponent_position("p1") == Coord(x=10.0, y=0.0)


def test_posesion_individual_y_de_equipo_con_companero(match_setup):
    engine = match_setup

    # p1 está cerca del balón al inicio
    assert engine.player_has_ball("p1") is True
    assert engine.team_has_ball("p1") is True

    # Movemos al aliado al radio de la pelota para simular cambio de posesion
    for _ in range(10):
        engine.apply_movement("aliado_1", Coord(x=0.5, y=0.0))

    assert engine.player_has_ball("aliado_1") is True
    assert engine.team_has_ball("p1") is True


def test_movimiento_desplazamiento_fisico_por_tick(match_setup):
    engine = match_setup
    expected_step = PLAYER_MAX_SPEED / settings.match_tick_rate

    # p1 tiene speed=100 (~0.6 unidades por tick). Intenta ir a (10.0, 0.0)
    engine.apply_movement("p1", Coord(x=10.0, y=0.0))

    pos = engine.player_position("p1")
    assert pos.x < 10.0  # No se teletransporta
    assert pos.x == pytest.approx(expected_step)


def test_pase_y_remate_desplazamiento_gradual_del_balon(match_setup):
    engine = match_setup

    # Remate al arco rival en (50.0, 0.0)
    engine.apply_shot("p1", Coord(x=50.0, y=0.0))
    assert engine._ball_velocity is not None

    ball_pos = engine.ball_position()
    expected_ball_step = BALL_MAX_POWER / settings.match_tick_rate    
    
    assert ball_pos.x == pytest.approx(0.5 + expected_ball_step)


def test_limite_de_cancha_centro_en_cero(match_setup):
    engine = match_setup

    assert engine.is_inside_field(Coord(x=0.0, y=0.0)) is True
    assert engine.is_inside_field(Coord(x=-50.0, y=-30.0)) is True
    assert engine.is_inside_field(Coord(x=50.0, y=30.0)) is True

    # Fuera del límite centrado en (0,0)
    assert engine.is_inside_field(Coord(x=-55.0, y=0.0)) is False
    assert engine.is_inside_field(Coord(x=55.0, y=0.0)) is False
    assert engine.is_inside_field(Coord(x=0.0, y=35.0)) is False


def test_disputa_de_pelota_gana_el_mas_cercano(match_setup):
    engine = match_setup
    # Movemos aliado a (0.7, 0.0)
    engine._players["aliado_1"].position = Coord(x=0.7, y=0.0)
    engine._update_possession_state()
    
    assert engine.player_has_ball("aliado_1") is True
    assert engine.player_has_ball("p1") is False


def test_conduccion_mantiene_posesion_varios_ticks(match_setup):
    engine = match_setup
    assert engine.player_has_ball("p1") is True

    # Realizamos conducción durante 5 ticks seguidos
    for _ in range(5):
        engine.apply_movement("p1", Coord(x=10.0, y=0.0))
        engine.advance_ball()
        assert engine.ball_position() == engine.player_position("p1")
        assert engine.player_has_ball("p1") is True


def test_remate_libera_posesion_y_se_detiene_en_destino(match_setup):
    engine = match_setup
    target = Coord(x=10.0, y=0.0)  # Objetivo cercano
    
    assert engine.player_has_ball("p1") is True

    engine.apply_shot("p1", target)

    # Inmediatamente al rematar pierde la posesión
    assert engine.player_has_ball("p1") is False

    # Corremos los ticks necesarios hasta que la pelota llegue al destino y se detenga
    max_ticks = 50
    ticks = 0
    while engine.ball_position() != target and ticks < max_ticks:
        engine.advance_ball()
        ticks += 1

    assert engine.ball_position() == target
    assert engine._ball_velocity is None
    assert engine._ball_target is None


def test_acciones_sin_pelota_o_fuera_de_limite_registran_error(match_setup):
    engine = match_setup

    # p1 intenta patear fuera de límites
    engine.apply_shot("p1", Coord(x=100.0, y=0.0))
    assert "p1" in engine._errors

    # aliado_1 intenta pasar sin tener la pelota
    engine.apply_pass("aliado_1", Coord(x=0.0, y=0.0))
    assert "aliado_1" in engine._errors