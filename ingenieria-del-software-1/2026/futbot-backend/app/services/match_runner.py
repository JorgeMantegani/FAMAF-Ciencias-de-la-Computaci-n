"""Motor y publicación de snapshots en el mismo proceso que el WebSocket."""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker
from app.db.base import ahora_utc
from app.engine.field import FieldConfig
from app.engine.live_state import match_states
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import MatchPhase, Team, publish_engine_tick
from app.models.match import ESTADO_IN_PROGRESS, ESTADO_PRE_MATCH, Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.schemas.match_state import MatchTick

logger = logging.getLogger(__name__)
Notifier = Callable[[str, dict], Awaitable[None]]
_running: dict[str, asyncio.Task] = {}


def build_engine_from_db(
    db: Session, match_id: str, cfg,
    notifier: Notifier | None = None,                                
) -> MatchEngine:
    match = db.get(Match, match_id)
    if match is None:
        raise LookupError(f"Partido {match_id} no existe")

    rows = db.execute(
        select(MatchPlayer, Player)
        .join(Player, Player.id == MatchPlayer.player_id)
        .where(MatchPlayer.match_id == match_id, MatchPlayer.on_field.is_(True))
        .order_by(MatchPlayer.id)                 # orden estable entre ejecuciones
    ).all()

    home, away, behaviors = [], [], {}
    for mp, pl in rows:
        spec = PlayerSpec(pl.id, pl.speed, pl.control, pl.strength, pl.power, pl.agility)
        (home if mp.club_id == match.home_club_id else away).append(spec)
        behaviors[pl.id] = mp.behavior_id

    field = FieldConfig()
    state = create_initial_state(field, home, away)      # valida 3 por equipo
    schedule = build_schedule(
        match.duration_seconds, cfg.match_tick_rate,
        hydration_seconds=match.pause_duration_seconds,
        halftime_seconds=match.pause_duration_seconds,
    )
    return MatchEngine(
        state, field, cfg, behaviors, schedule=schedule,
    )


def capture_tick(engine, roster, club_of, previous_goals=0):
    state, field = engine.state, engine.field
    def position(point):
        return {"x": (point.x / field.length - .5) * 100,
                "y": (point.y / field.width - .5) * 60}
    active = {player.id: player for player in state.players}
    status = ("finished" if state.phase == MatchPhase.FINISHED else
              "paused" if state.phase in (MatchPhase.HYDRATION, MatchPhase.HALFTIME)
              else "in_progress")
    return MatchTick.model_validate({
        "status": status,
        "current_time": state.play_ticks / engine.cfg.match_tick_rate,
        "score": {"home": state.score[Team.HOME], "away": state.score[Team.AWAY]},
        "players": [{"player_id": pid, "on_field": pid in active,
                     "position": position(active[pid].pos) if pid in active else None}
                    for pid in roster],
        "ball": {**position(state.ball.pos), "owner_player_id": state.ball.owner_id,
                 "vx": state.ball.vel.x * 100 / field.length,
                 "vy": state.ball.vel.y * 60 / field.width},
        "actions": [{"type": "goal", "club_id": club_of[g.team], "player_id": g.player_id}
                    for g in state.goals[previous_goals:]],
    })


async def _play(match_id, engine, roster, club_of, sessions, notifier):
    revision, goals = 1, 0
    loop = asyncio.get_running_loop()
    deadline = loop.time()
    try:
        while engine.state.phase != MatchPhase.FINISHED:
            await engine.tick()
            with sessions() as db:
                published = publish_engine_tick(
                    db, match_id, capture_tick(engine, roster, club_of, goals),
                    expected_revision=revision)
            revision, goals = published.revision, len(engine.state.goals)
            deadline += engine.dt
            await asyncio.sleep(max(0, deadline - loop.time()) if engine.realtime else 0)
        if notifier:
            await notifier(match_id, {
                "type": "MATCH_FINISHED", "match_id": match_id,
                "home_goals": engine.state.score[Team.HOME],
                "away_goals": engine.state.score[Team.AWAY],
                "goals": [{"club_id": club_of[g.team], "player_id": g.player_id,
                           "second": g.second} for g in engine.state.goals]})
    finally:
        engine.close()


def _completed(match_id, task):
    if _running.get(match_id) is task:
        _running.pop(match_id, None)
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.error("Falló el motor del partido %s", match_id,
                     exc_info=(type(error), error, error.__traceback__))


def start_match(db: Session, match_id: str, cfg, notifier: Notifier | None = None) -> None:
    """Publica el estado inicial antes de responder y ejecuta ticks en el loop de la API."""
    loop = asyncio.get_running_loop()
    if match_id in _running or match_states.get(match_id) is not None:
        raise RuntimeError("El partido ya está en curso o tiene un estado publicado")
    match = db.get(Match, match_id)
    if match is None:
        raise LookupError(f"Partido {match_id} no existe")
    if match.status not in (ESTADO_PRE_MATCH, ESTADO_IN_PROGRESS) or match.home_goals or match.away_goals:
        raise RuntimeError("El partido no se puede iniciar desde cero")
    engine = build_engine_from_db(db, match_id, cfg)
    try:
        roster = list(db.scalars(select(MatchPlayer.player_id).where(MatchPlayer.match_id == match_id)))
        club_of = {Team.HOME: match.home_club_id, Team.AWAY: match.away_club_id}
        sessions = sessionmaker(bind=db.get_bind(), autoflush=False)
        match.status = ESTADO_IN_PROGRESS
        match.started_at = match.started_at or ahora_utc()
        db.execute(update(Player).where(Player.id.in_(roster)).values(is_playing=True))
        db.commit()
        engine.start()
        publish_engine_tick(db, match_id, capture_tick(engine, roster, club_of), expected_revision=0)
        task = loop.create_task(_play(match_id, engine, roster, club_of, sessions, notifier),
                                name=f"match-{match_id}")
        _running[match_id] = task
        task.add_done_callback(lambda done: _completed(match_id, done))
    except BaseException:
        engine.close()
        raise


async def stop_matches():
    tasks = list(_running.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
