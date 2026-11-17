"""Fase y duración de la pausa en el tick que arma el runner a partir del motor."""
from uuid import uuid4

import pytest

from app.behaviors import executor
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import MatchPhase, Team
from app.services.match_runner import capture_tick

from app.services.match_runner import build_engine_from_db
from app.behaviors import loader
from app.core.config import get_settings


CLUB_OF = {Team.HOME: str(uuid4()), Team.AWAY: str(uuid4())}


class Cfg:
    behavior_timeout_seconds = 0.05
    match_tick_rate = 10
    friendly_match_duration_seconds = 8


def specs():
    return [PlayerSpec(str(uuid4()), 60, 60, 60, 60, 60) for _ in range(3)]


@pytest.fixture
def match_engine(monkeypatch):
    monkeypatch.setattr(executor, "ejecutar_comportamiento", lambda pid, ctx: None)
    field = FieldConfig()
    state = create_initial_state(field, specs(), specs())
    # Pausas de distinta duración: hidratación 1 s, entretiempo 2 s.
    schedule = build_schedule(8, 10, hydration_seconds=1, halftime_seconds=2)
    engine = MatchEngine(state, field, Cfg(), {p.id: "b" for p in state.players},
                         schedule=schedule, realtime=False)
    yield engine
    engine.close()


@pytest.mark.asyncio
async def test_each_tick_reports_phase_and_pause_times(match_engine):
    roster = [p.id for p in match_engine.state.players]
    match_engine.start()
    ticks = [capture_tick(match_engine, roster, CLUB_OF)]
    for _ in range(500):
        if match_engine.state.phase == MatchPhase.FINISHED:
            break
        await match_engine.tick()
        ticks.append(capture_tick(match_engine, roster, CLUB_OF))

    pairs = [(tick.phase, tick.pause_duration) for tick in ticks]
    collapsed = [pair for i, pair in enumerate(pairs) if i == 0 or pair != pairs[i - 1]]
    assert collapsed == [
        ("PLAYING", None), ("HYDRATION", 1),
        ("PLAYING", None), ("HALFTIME", 2),
        ("PLAYING", None), ("HYDRATION", 1),
        ("PLAYING", None), ("FINISHED", None),
    ]

    hydration = [tick.pause_remaining for tick in ticks if tick.phase == "HYDRATION"]
    halftime = [tick.pause_remaining for tick in ticks if tick.phase == "HALFTIME"]
    # Each pause counts down from its total to one tick (0.1 s), never reaching 0.
    assert hydration == pytest.approx([1 - i / 10 for i in range(10)] * 2)
    assert halftime == pytest.approx([2 - i / 10 for i in range(20)])

@pytest.mark.asyncio
async def test_partido_carga_comportamiento_personalizado(
    db, club_players, behavior_personalizado, match_en_pre_match, monkeypatch
):
   # Parchea la cache
    monkeypatch.setattr(loader, "_cache", {})
    
    engine = build_engine_from_db(db, match_id=match_en_pre_match.id, cfg=get_settings())
    
    # Valida verificando la cache dentro del módulo
    assert behavior_personalizado.id in loader._cache
    
    engine.start()
    
    # Busca al jugador y guarda su posición inicial
    jugador = next(p for p in engine.state.players if p.id == club_players[0].id)
    pos_x_inicial = jugador.pos.x
    pos_y_inicial = jugador.pos.y
    
    await engine.tick() 
    
    # Verifica que se movió
    assert jugador.pos.x != pos_x_inicial or jugador.pos.y != pos_y_inicial


@pytest.mark.asyncio
async def test_edicion_de_comportamiento_pisa_cache(
    db, club_players, behavior_personalizado, match_en_pre_match, monkeypatch
):
    monkeypatch.setattr(loader, "_cache", {})
    
    # Simula basura en la cache
    loader.compile_and_cache_behavior(
        behavior_personalizado.id, 
        "def behavior(player):\n    pass" 
    )
    
    # El usuario edita su codigo en la base de datos
    behavior_personalizado.code = """
def behavior(player):
    pelota = player.encontrar_pelota()
    player.correr(pelota)
"""
    db.commit()
    
    engine = build_engine_from_db(db, match_id=match_en_pre_match.id, cfg=get_settings())
    engine.start()
    
    jugador = next(p for p in engine.state.players if p.id == club_players[0].id)
    pos_x_inicial = jugador.pos.x
    pos_y_inicial = jugador.pos.y
    
    await engine.tick()
    
    # Ve si se usó el código nuevo (se movió) y no el código vacío
    assert jugador.pos.x != pos_x_inicial or jugador.pos.y != pos_y_inicial