"""Punto de integración del motor: ticks en memoria y eventos durables."""
from collections import Counter
from typing import Protocol

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from app.db.base import ahora_utc
from app.engine.live_state import match_states
from app.models.goal import Goal
from app.models.match import ESTADO_IN_PROGRESS, ESTADO_PAUSED, Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import Room
from app.schemas.match_state import MatchState, MatchTick
from app.services.match_state import prepare_match_state, publish_prepared_state
from dataclasses import dataclass, field
from enum import Enum
import math


class Team(str, Enum):
    HOME = "home"
    AWAY = "away"

class MatchPhase(str, Enum):
    PRE = "pre"
    PLAY = "play"
    HYDRATION = "hydration"
    HALFTIME = "halftime"
    FINISHED = "finished"

class MatchStateSource(Protocol):
    def capture_state(self) -> MatchTick:
        """Captura un tick completo bajo el lock del motor, después de las acciones."""
        ...


def publish_engine_state(db: Session, match_id: str, engine: MatchStateSource, *, expected_revision: int) -> MatchState:
    return publish_engine_tick(db, match_id, engine.capture_state(), expected_revision=expected_revision)


def publish_engine_tick(db: Session, match_id: str, tick: MatchTick, *, expected_revision: int) -> MatchState:
    """Usar una sesión limpia y datos de creación ya confirmados.

    Solo hace commit ante goles o cambios de estado (pausa/reanudación/fin).
    Un fallo al persistir no publica el snapshot ni avanza su revisión.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError('El motor requiere una sesión sin cambios pendientes')
    with match_states.lock(match_id):
        state = prepare_match_state(db, match_id, tick, expected_revision=expected_revision)
        match = db.get(Match, match_id)
        goals = [action for action in state.actions if action.type == 'goal']
        counts = Counter(str(goal.club_id) for goal in goals)
        expected = Counter({
            match.home_club_id: state.score.home - match.home_goals,
            match.away_club_id: state.score.away - match.away_goals,
        })
        if any(count < 0 for count in expected.values()) or counts != expected:
            raise ValueError('Cada incremento del marcador requiere su evento de gol con club')
        significant = bool(goals) or match.status != state.status
        if significant:
            try:
                for goal in goals:
                    scorer = next((p for p in state.players if p.player_id == goal.player_id), None)
                    # En un gol en contra no se atribuye el gol al jugador rival.
                    scorer_id = str(scorer.player_id) if scorer and scorer.club_id == goal.club_id else None
                    db.add(Goal(match_id=match_id, club_id=str(goal.club_id), player_id=scorer_id,
                                second=int(state.current_time)))
                    if scorer_id:
                        entry = db.scalar(select(MatchPlayer).where(MatchPlayer.match_id == match_id, MatchPlayer.player_id == scorer_id))
                        entry.goals += 1
                match.home_goals, match.away_goals = state.score.home, state.score.away
                match.status = state.status
                if state.status == 'finished':
                    match.finished_at = ahora_utc()
                    room = db.get(Room, match.room_id)
                    if room.type == 'friendly':
                        room.status, room.finished_at = 'finished', match.finished_at
                    roster_ids = select(MatchPlayer.player_id).where(
                        MatchPlayer.match_id == match_id
                    )
                    active_elsewhere = exists(
                        select(1)
                        .select_from(MatchPlayer)
                        .join(Match, Match.id == MatchPlayer.match_id)
                        .where(
                            MatchPlayer.player_id == Player.id,
                            MatchPlayer.match_id != match_id,
                            Match.status.in_((ESTADO_IN_PROGRESS, ESTADO_PAUSED)),
                        )
                    )
                    db.execute(
                        update(Player)
                        .where(Player.id.in_(roster_ids), ~active_elsewhere)
                        .values(is_playing=False)
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
        publish_prepared_state(state)
        return state

@dataclass(frozen=True, slots=True) #vector 2D
class Vec2:
    x: float = 0.0
    y: float = 0.0

    #metodos especiales de suma, resta y multiplicacion
    def __add__(self, o: "Vec2") -> "Vec2": return Vec2(self.x + o.x, self.y + o.y)
    def __sub__(self, o: "Vec2") -> "Vec2": return Vec2(self.x - o.x, self.y - o.y)
    def __mul__(self, k: float) -> "Vec2": return Vec2(self.x * k, self.y * k)
    __rmul__ = __mul__
    
    def length(self) -> float: return math.hypot(self.x, self.y)
    
    def normalized(self) -> "Vec2":
        n = self.length()
        return Vec2(0.0, 0.0) if n == 0 else Vec2(self.x / n, self.y / n)
    
    #limita el tamaño maximo del vector, si es mayor lo escala a max_len
    def clamp_length(self, max_len: float) -> "Vec2":
        n = self.length()
        return self if n <= max_len else self * (max_len / n)

@dataclass(frozen=True, slots=True)
class GoalEvent:
    team: Team                 # equipo que suma el punto
    player_id: str | None      # autor; None si es gol en contra o no hay autor claro
    second: int                # segundo de juego (sin contar pausas)

@dataclass
class PlayerState:
    slots=True
    id: str 
    team: Team
    pos: Vec2
    speed: float
    control: float
    strength: float
    power: float
    agility: float
    vel: Vec2 = field(default_factory=Vec2)

@dataclass(slots=True)
class BallState:
    pos: Vec2
    vel: Vec2 = field(default_factory=Vec2)
    owner_id: str | None = None   # quién la controla, None si está libre
    last_kicker_id: str | None = None
    cooldown_ticks: int = 0  
    
@dataclass(slots=True)
class MatchState:
    players: list[PlayerState]
    ball: BallState
    score: dict[Team, int] = field(
        default_factory=lambda: {Team.HOME: 0, Team.AWAY: 0}
    )
    phase: MatchPhase = MatchPhase.PRE
    period: int = 0              # 1 a 4 (0 antes de empezar)
    tick_count: int = 0          # ticks totales del partido
    phase_tick: int = 0          # ticks transcurridos en la fase actual
    play_ticks: int = 0          # solo ticks de juego (para el reloj visible)
    goals: list[GoalEvent] = field(default_factory=list)
   
