import pytest
from app.schemas.coord import Coord
from app.core.config import settings
from app.engine.primitives import MatchEngine, PlayerState, PLAYER_MAX_SPEED
from app.behaviors.executor import ejecutar_comportamiento
from app.behaviors.loader import _cache


@pytest.fixture
def integration_setup():
    players_data = {
        "p1": PlayerState(
            club_id="CLUB_A",
            position=Coord(x=0.0, y=0.0),
            own_goal=Coord(x=-50.0, y=0.0),
            enemy_goal=Coord(x=50.0, y=0.0),
            speed=100,
            power=100,
            control=100,
            is_on_field=True,
            behavior_id="beh_delantero_test",
        ),
        "aliado_1": PlayerState(
            club_id="CLUB_A",
            position=Coord(x=10.0, y=0.0),
            own_goal=Coord(x=-50.0, y=0.0),
            enemy_goal=Coord(x=50.0, y=0.0),
            speed=60,
            power=60,
            control=60,
            is_on_field=True,
            behavior_id="beh_aliado_test",
        ),
    }
    ball_pos = Coord(x=0.2, y=0.0)  # p1 tiene la pelota
    engine = MatchEngine(players_data, ball_pos)
    return engine


def test_integracion_executor_y_comportamiento_ofensivo(integration_setup, monkeypatch):
    engine = integration_setup

    def script_delantero(player):
        if player.tengo_pelota():
            arco = player.encontrar_arco_enemigo()
            player.patear_pelota(arco)

    # Uso correcto de monkeypatch para no dejar basura en el caché global
    monkeypatch.setitem(_cache, "beh_delantero_test", script_delantero)

    ejecutar_comportamiento("p1", engine)
    engine.advance_ball()

    # Verifica avance físico del balón sin teletransporte completo
    assert engine.ball_position().x > 0.2
    assert engine.ball_position().x < 50.0


def test_integracion_executor_movimiento_sin_pelota(monkeypatch):
    players_data = {
        "p1": PlayerState(
            club_id="CLUB_A",
            position=Coord(x=0.0, y=0.0),
            own_goal=Coord(x=-50.0, y=0.0),
            enemy_goal=Coord(x=50.0, y=0.0),
            speed=100,
            power=100,
            control=100,
            is_on_field=True,
            behavior_id="beh_corredor_test",
        ),
    }
    engine = MatchEngine(players_data, Coord(x=20.0, y=0.0))

    def script_correr_a_pelota(player):
        if not player.tengo_pelota():
            pelota = player.encontrar_pelota()
            player.correr(pelota)

    monkeypatch.setitem(_cache, "beh_corredor_test", script_correr_a_pelota)

    ejecutar_comportamiento("p1", engine)

    # verifica avance exacto en 1 tick
    expected_step = PLAYER_MAX_SPEED / settings.match_tick_rate
    assert engine.player_position("p1").x == pytest.approx(expected_step)