"""Lectura autorizada y publicacion atomica del estado completo de un tick."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.match import Match
from app.models.match_player import MatchPlayer
from app.engine.live_state import match_states
from app.ws.manager import manager
from app.models.player import Player
from app.models.user import User
from app.schemas.match_state import ClubState, MatchState, MatchTick, PlayerState


class MatchNotFound(Exception):
    pass


class MatchAccessDenied(Exception):
    pass


class MatchStateUnavailable(Exception):
    pass


class StaleMatchState(Exception):
    pass


def authorize_match(db: Session, match_id: str, user: User) -> Match:
    """Valida acceso sin consultar el estado en vivo."""
    match = db.get(Match, match_id)
    if match is None:
        raise MatchNotFound
    club_id = db.scalar(select(Club.id).where(Club.user_id == user.id))
    if club_id not in (match.home_club_id, match.away_club_id):
        raise MatchAccessDenied
    return match


def get_match_state(db: Session, match_id: str, user: User) -> MatchState:
    authorize_match(db, match_id, user)
    state = match_states.get(match_id)
    if state is None:
        raise MatchStateUnavailable
    return state


def publish_match_state(
    db: Session, match_id: str, tick: MatchTick, *, expected_revision: int
) -> MatchState:
    """Publica solo en memoria y avisa a los sockets, sin flush ni commit.

    El motor debe usar publish_engine_tick para persistir goles/transiciones.
    La publicación es inmediata: un rollback de SQL no revierte un tick en vivo.
    """
    with match_states.lock(match_id):
        state = prepare_match_state(db, match_id, tick, expected_revision=expected_revision)
        publish_prepared_state(state)
        return state


def publish_prepared_state(state: MatchState) -> None:
    """Llamar bajo el lock del partido, tras persistir los eventos si corresponde."""
    match_states.put(state)
    manager.broadcast(state)


def prepare_match_state(db: Session, match_id: str, tick: MatchTick, *, expected_revision: int) -> MatchState:
    """Valida y construye un snapshot sin escribir; requiere el lock del partido."""
    if expected_revision < 0:
        raise ValueError("La revision no puede ser negativa")
    tick = MatchTick.model_validate(tick.model_dump())
    match = db.get(Match, match_id)
    if match is None:
        raise MatchNotFound
    if match.status not in ("in_progress", "paused", "finished"):
        raise ValueError("El partido todavia no fue iniciado")
    if tick.current_time > match.duration_seconds:
        raise ValueError("El tiempo supera la duracion del partido")
    previous = match_states.get(match_id)
    if previous is not None:
        if previous.revision != expected_revision:
            raise StaleMatchState
        if previous.status == "finished":
            raise ValueError("El partido ya termino")
        if tick.current_time < previous.current_time:
            raise ValueError("El tiempo no puede retroceder")
    elif expected_revision != 0:
        raise StaleMatchState
    if match.status == "finished" and tick.status != "finished":
        raise ValueError("No se puede reabrir un partido terminado")

    roster = db.execute(select(MatchPlayer, Player).join(
        Player, MatchPlayer.player_id == Player.id
    ).where(MatchPlayer.match_id == match_id)).all()
    ticks = {str(player.player_id): player for player in tick.players}
    if len(ticks) != len(tick.players) or set(ticks) != {entry.player_id for entry, _ in roster}:
        raise ValueError("El tick debe incluir exactamente los jugadores del partido, sin duplicados")
    clubs = {match.home_club_id, match.away_club_id}
    if any(entry.club_id not in clubs or player.club_id != entry.club_id for entry, player in roster):
        raise ValueError("La alineacion contiene jugadores de otro club")
    owner = str(tick.ball.owner_player_id) if tick.ball.owner_player_id else None
    if owner is not None and (owner not in ticks or not ticks[owner].on_field):
        raise ValueError("El poseedor de la pelota debe estar en cancha")
    for action in tick.actions:
        if action.player_id is not None and str(action.player_id) not in ticks:
            raise ValueError("La accion pertenece a un jugador ajeno al partido")
        if action.club_id is not None and str(action.club_id) not in clubs:
            raise ValueError("La accion pertenece a un club ajeno al partido")
    home = db.get(Club, match.home_club_id)
    away = db.get(Club, match.away_club_id)
    state = MatchState(
        match_id=match.id, revision=expected_revision + 1,
        home_club=ClubState(club_id=home.id, name=home.name),
        away_club=ClubState(club_id=away.id, name=away.name),
        status=tick.status, score=tick.score,
        result=f"{tick.score.home}-{tick.score.away}",
        current_time=tick.current_time,
        remaining_time=max(0, match.duration_seconds - tick.current_time),
        duration_seconds=match.duration_seconds,
        ball=tick.ball, actions=tick.actions,
        players=[PlayerState(
            **ticks[entry.player_id].model_dump(), club_id=entry.club_id,
            name=player.name, behavior_id=entry.behavior_id,
            has_ball=owner == entry.player_id,
        ) for entry, player in sorted(roster, key=lambda row: row[0].player_id)],
    )
    return state
