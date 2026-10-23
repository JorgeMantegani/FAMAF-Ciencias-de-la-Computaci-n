# scripts/simulate.py
import asyncio
import random

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registra las tablas)
from app.behaviors import loader                      # ajustá la ruta si difiere
from app.core.config import get_settings
from app.db.base import Base
from app.db.init_db import cargar_comportamientos_por_defecto
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import MatchPhase, Team
from app.models.behavior import Behavior

# Perfiles válidos: cada uno suma 300 y respeta 20-100
PROFILES = [
    (80, 60, 50, 60, 50),   # rápido
    (50, 60, 70, 70, 50),   # fuerte
    (60, 80, 50, 50, 60),   # técnico
]


def specs(prefix: str) -> list[PlayerSpec]:
    return [PlayerSpec(f"{prefix}{i}", *PROFILES[i]) for i in range(3)]


def load_behavior_ids() -> list[str]:
    db_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db_engine)
    with Session(db_engine) as db:
        cargar_comportamientos_por_defecto(db)
        loader.precargar_preprogramados(db)
        return [b.id for b in db.scalars(select(Behavior)).all()]


async def play(seed: int, cfg, behavior_ids: list[str]) -> None:
    field = FieldConfig()
    state = create_initial_state(field, specs("h"), specs("a"))
    behaviors = {p.id: behavior_ids[i % len(behavior_ids)]
                 for i, p in enumerate(state.players)}
    eng = MatchEngine(state, field, cfg, behaviors,
                      rng=random.Random(seed), realtime=False)

    poss = {Team.HOME: 0, Team.AWAY: 0, None: 0}
    team_of = {p.id: p.team for p in state.players}
    kicks = takes = 0
    prev_owner = None

    eng.start()
    try:
        while state.phase != MatchPhase.FINISHED:
            await eng.tick()
            owner = state.ball.owner_id
            if owner is not None and prev_owner is None:
                takes += 1
            if owner is None and prev_owner is not None:
                kicks += 1
            prev_owner = owner
            if state.phase == MatchPhase.PLAY:
                poss[team_of.get(owner)] += 1
    finally:
        eng.close()

    total = sum(poss.values()) or 1
    print(f"seed={seed}  {state.score[Team.HOME]}-{state.score[Team.AWAY]}  "
          f"ticks={state.tick_count}  takes={takes} kicks={kicks}  "
          f"posesión H/A/libre = {poss[Team.HOME]*100//total}%/"
          f"{poss[Team.AWAY]*100//total}%/{poss[None]*100//total}%")

async def main() -> None:
    cfg = get_settings()
    ids = load_behavior_ids()
    for seed in range(10):
        await play(seed, cfg, ids)


if __name__ == "__main__":
    asyncio.run(main())