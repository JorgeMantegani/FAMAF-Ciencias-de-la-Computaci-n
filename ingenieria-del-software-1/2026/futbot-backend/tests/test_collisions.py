import math
from types import SimpleNamespace as NS

from app.engine.collisions import resolve_player_collisions
from app.engine.state import PlayerState, Team, Vec2

R = 0.5
FIELD = NS(length=105.0, width=68.0)


def jugador(pid, team, x, y, strength=50):
    return PlayerState(id=pid, team=team, pos=Vec2(x, y), speed=50,
                       control=50, strength=strength, power=50, agility=50)


def dist(a, b):
    return math.hypot(a.pos.x - b.pos.x, a.pos.y - b.pos.y)


def test_separa_solapados():
    a, b = jugador("a", Team.HOME, 50, 30), jugador("b", Team.AWAY, 50.4, 30)
    resolve_player_collisions([a, b], FIELD, R)
    assert dist(a, b) >= 2 * R - 1e-9


def test_sin_solape_no_toca_nada():
    a, b = jugador("a", Team.HOME, 10, 10), jugador("b", Team.AWAY, 20, 10)
    pa, pb = a.pos, b.pos
    resolve_player_collisions([a, b], FIELD, R)
    assert (a.pos, b.pos) == (pa, pb)


def test_el_mas_fuerte_se_mueve_menos():
    a = jugador("a", Team.HOME, 50, 30, strength=80)
    b = jugador("b", Team.AWAY, 50.4, 30, strength=20)
    resolve_player_collisions([a, b], FIELD, R)
    assert abs(a.pos.x - 50) < abs(b.pos.x - 50.4)


def test_igual_fuerza_se_mueven_lo_mismo():
    a, b = jugador("a", Team.HOME, 50, 30), jugador("b", Team.AWAY, 50.4, 30)
    resolve_player_collisions([a, b], FIELD, R)
    assert math.isclose(abs(a.pos.x - 50), abs(b.pos.x - 50.4))


def test_companeros_tambien_colisionan():
    a, b = jugador("a", Team.HOME, 50, 30), jugador("b", Team.HOME, 50.4, 30)
    resolve_player_collisions([a, b], FIELD, R)
    assert dist(a, b) >= 2 * R - 1e-9


def test_misma_posicion_no_explota():
    a, b = jugador("a", Team.HOME, 50, 30), jugador("b", Team.AWAY, 50, 30)
    resolve_player_collisions([a, b], FIELD, R)
    assert dist(a, b) >= 2 * R - 1e-9


def test_no_se_sale_de_la_cancha():
    a, b = jugador("a", Team.HOME, 0.1, 30), jugador("b", Team.AWAY, 0.3, 30)
    resolve_player_collisions([a, b], FIELD, R)
    assert all(0 <= p.pos.x <= FIELD.length and 0 <= p.pos.y <= FIELD.width for p in (a, b))


def test_tres_jugadores_apilados_terminan_separados():
    ps = [jugador("a", Team.HOME, 50.0, 30), jugador("b", Team.AWAY, 50.2, 30),
          jugador("c", Team.AWAY, 50.4, 30)]
    resolve_player_collisions(ps, FIELD, R, iterations=10)
    assert all(dist(ps[i], ps[j]) >= 2 * R - 1e-3
               for i in range(3) for j in range(i + 1, 3))