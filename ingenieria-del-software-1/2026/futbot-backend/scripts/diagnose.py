import asyncio
import random
import time
from types import SimpleNamespace

from app.behaviors import executor
from app.engine.action import NULL_ACTION
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.setup import create_initial_state
from app.engine.tick_context import TickContext
from scripts.simulate import specs, load_behavior_ids


async def main() -> None:
    ids = load_behavior_ids()
    field = FieldConfig()
    state = create_initial_state(field, specs("h"), specs("a"))
    behaviors = {p.id: ids[i % len(ids)] for i, p in enumerate(state.players)}

    # 1. Cuánto tarda un bot, sin hilos ni timeout
    ctx = TickContext(state, field, behaviors)
    for p in state.players:
        t0 = time.perf_counter()
        executor.ejecutar_comportamiento(p.id, ctx)
        ms = (time.perf_counter() - t0) * 1000
        print(f"{p.id}: {ms:.2f} ms  acción={ctx.action_for(p.id)}  errores={ctx.errors}")

    # 2. Cuántos bots actúan por tick, con distintos timeouts
    for timeout in (0.05, 0.5):
        cfg = SimpleNamespace(match_tick_rate=15, friendly_match_duration_seconds=300,
                              behavior_timeout_seconds=timeout)
        st = create_initial_state(field, specs("h"), specs("a"))
        eng = MatchEngine(st, field, cfg, behaviors, rng=random.Random(0), realtime=False)
        eng.start()
        active = 0
        for _ in range(100):
            acts = await eng._collect_actions()
            active += sum(a is not NULL_ACTION for a in acts.values())
            await eng.tick()
        eng.close()
        print(f"timeout={timeout}: {active/100:.1f} de 6 bots con acción por tick")


asyncio.run(main())