"""Motor y publicación de snapshots en el mismo proceso que el WebSocket."""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker
from app.db.base import ahora_utc
from app.engine.field import FieldConfig
from app.engine.live_state import match_states
from app.engine.match_engine import MatchEngine, PENALTY_MAX_SECONDS
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import MatchPhase, PlayerState, Team, Vec2, publish_engine_tick
from app.models.match import ESTADO_IN_PROGRESS, ESTADO_PRE_MATCH, Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.behaviors.loader import compile_and_cache_behavior
from app.models.behavior import Behavior
from app.models.room import Room
from app.schemas.match_state import PHASE_STATUS, MatchTick
from app.ws.manager import manager

logger = logging.getLogger(__name__)
Notifier = Callable[[str, dict], Awaitable[None]]
_running: dict[str, asyncio.Task] = {}
_engines: dict[str, MatchEngine] = {}
_match_club_teams: dict[str, dict[str, Team]] = {}
TICK_PHASES = {
    MatchPhase.PLAY: "PLAYING",
    MatchPhase.HYDRATION: "HYDRATION",
    MatchPhase.HALFTIME: "HALFTIME",
    MatchPhase.PENALTIES: "PENALTIES",
    MatchPhase.FINISHED: "FINISHED",
}

def get_live_engine(match_id: str) -> MatchEngine | None:
    return _engines.get(match_id)

def build_engine_from_db(
    db: Session, match_id: str, cfg,
    notifier: Notifier | None = None,                                
) -> MatchEngine:
    match = db.get(Match, match_id)
    if match is None:
        raise LookupError(f"Partido {match_id} no existe")
    room = db.get(Room, match.room_id)
    if room is None:
        raise LookupError(f"Sala {match.room_id} del partido no existe")

    rows = db.execute(
        select(MatchPlayer, Player)
        .join(Player, Player.id == MatchPlayer.player_id)
        .where(MatchPlayer.match_id == match_id)
        .order_by(MatchPlayer.id)
    ).all()

    home, away, behaviors = [], [], {}
    substitutes: dict[Team, list[PlayerSpec]] = {Team.HOME: [], Team.AWAY: []}
    for mp, pl in rows:
        spec = PlayerSpec(pl.id, pl.speed, pl.control, pl.strength, pl.power, pl.agility)
        team = Team.HOME if mp.club_id == match.home_club_id else Team.AWAY
        if mp.on_field:
            (home if team == Team.HOME else away).append(spec)
        else:
            substitutes[team].append(spec)
        behaviors[pl.id] = mp.behavior_id

    behavior_ids = set(behaviors.values())
    if behavior_ids:
        # Buscamos los comportamientos en la base de datos
        behavior_rows = db.scalars(
            select(Behavior).where(
                Behavior.id.in_(behavior_ids),
                Behavior.deleted_at.is_(None)
            )
        ).all()

        # Validamos que no falte ninguno
        found_ids = {b.id for b in behavior_rows}
        missing_ids = behavior_ids - found_ids

        if missing_ids:
            raise LookupError(f"Comportamientos no encontrados en la DB: {missing_ids}")

        # Los compilamos y forzamos a guardarlos en caché
        for behavior in behavior_rows:
            compile_and_cache_behavior(
                behavior_id=behavior.id,
                code=behavior.code,
                overwrite=True  # Pisa la versión vieja si el usuario lo editó
            )
    
    field = FieldConfig()
    state = create_initial_state(field, home, away)      # valida 3 por equipo
    schedule = build_schedule(
        match.duration_seconds, cfg.match_tick_rate,
        hydration_seconds=match.pause_duration_seconds,
        halftime_seconds=match.pause_duration_seconds,
    )
    engine = MatchEngine(
        state,
        field,
        cfg,
        behaviors,
        schedule=schedule,
        has_penalty_shootout=room.has_penalty_shootout,
        club_ids={Team.HOME: match.home_club_id, Team.AWAY: match.away_club_id},
    )
    for team, specs in substitutes.items():
        for spec in specs:
            engine.set_substitute(
                team,
                spec.id,
                PlayerState(
                    id=spec.id,
                    team=team,
                    pos=Vec2(),
                    speed=spec.speed,
                    control=spec.control,
                    strength=spec.strength,
                    power=spec.power,
                    agility=spec.agility,
                ),
            )
    engine.on_ws_event = lambda event: manager.broadcast_event(match_id, event)
    return engine


def request_match_substitution(
    match_id: str, club_id: str, out_player_id: str | int, in_player_id: str | int
) -> dict:
    engine = _engines.get(match_id)
    if engine is None:
        return {
            "type": "error",
            "ok": False,
            "error_code": "SUBSTITUTION_ENGINE_UNAVAILABLE",
            "message": "El partido no tiene un motor activo",
        }
    team = _match_club_teams.get(match_id, {}).get(club_id)
    if team is None:
        return {
            "type": "error",
            "ok": False,
            "error_code": "SUBSTITUTION_CLUB_NOT_IN_MATCH",
            "message": "El club no participa en este partido",
        }
    return engine.request_substitution(team, out_player_id, in_player_id)


def get_match_substitution_state(match_id: str, club_id: str) -> dict | None:
    engine = _engines.get(match_id)
    if engine is None:
        return None
    team = _match_club_teams.get(match_id, {}).get(club_id)
    if team is None:
        return None

    pending = engine.pending_substitution[team]
    return {
        "type": "SUBSTITUTION_STATE",
        "pendingSubstitution": dict(pending) if pending is not None else None,
        "changesUsedThisPause": engine.changes_used_this_pause[team],
    }


def capture_tick(engine, roster, club_of, previous_goals=0):
    state, field = engine.state, engine.field
    def position(point):
        return {"x": (point.x / field.length - .5) * 100,
                "y": (point.y / field.width - .5) * 60}
    active = {player.id: player for player in state.players}
    phase = TICK_PHASES[state.phase]
    penalty = None
    if engine._penalty_full_roster is not None:
        penalty = {
            "shooter_id": engine._penalty_shooter.id if engine._penalty_shooter else None,
            "goalkeeper_id": engine._penalty_goalkeeper.id if engine._penalty_goalkeeper else None,
            "score": {
                Team.HOME.value: engine.penalty_score[Team.HOME],
                Team.AWAY.value: engine.penalty_score[Team.AWAY],
            },
            "attempts": {
                Team.HOME.value: engine.penalty_attempts[Team.HOME],
                Team.AWAY.value: engine.penalty_attempts[Team.AWAY],
            },
            "seconds_remaining": max(
                0,
                PENALTY_MAX_SECONDS - engine._penalty_ticks * engine.dt,
            ) if state.phase == MatchPhase.PENALTIES else 0,
            "winner_club_id": (
                club_of[engine.penalty_winner]
                if engine.penalty_winner is not None else None
            ),
        }
    return MatchTick.model_validate({
        "status": PHASE_STATUS[phase],
        "phase": phase,
        "penalty": penalty,
        "pause_duration": engine.pause_seconds,
        "pause_remaining": engine.pause_remaining_seconds,
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
            previous_phase = engine.state.phase
            deferred_events = []
            event_callback = engine.on_ws_event
            engine.on_ws_event = deferred_events.append
            try:
                await engine.tick()
            finally:
                engine.on_ws_event = event_callback
            with sessions() as db:
                published = publish_engine_tick(
                    db, match_id, capture_tick(engine, roster, club_of, goals),
                    expected_revision=revision,
                    penalty_winner_club_id=(
                        club_of[engine.penalty_winner]
                        if engine.penalty_winner is not None else None
                    ),
                    events=deferred_events,
                )
            revision, goals = published.revision, len(engine.state.goals)
            if (
                engine.realtime
                and previous_phase != MatchPhase.PENALTIES
                and engine.state.phase == MatchPhase.PENALTIES
            ):
                await asyncio.sleep(1)
                deadline = loop.time()
                continue
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
        _engines.pop(match_id, None)
        _match_club_teams.pop(match_id, None)
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
        _engines[match_id] = engine
        _match_club_teams[match_id] = {
            match.home_club_id: Team.HOME,
            match.away_club_id: Team.AWAY,
        }
        task.add_done_callback(lambda done: _completed(match_id, done))
    except BaseException:
        engine.close()
        raise


async def stop_matches():
    tasks = list(_running.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
