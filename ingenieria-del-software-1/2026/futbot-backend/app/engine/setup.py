from dataclasses import dataclass

from app.engine.field import FieldConfig
from app.engine.state import (
    BallState, MatchState, PlayerState, Team, Vec2,
)
from app.engine.constants import ATTR_MAX, ATTR_MIN, ATTR_NAMES, ATTR_TOTAL

# Formación de 3 jugadores, definida para HOME (ataca hacia x = length).
# Cada slot es (fracción del largo, fracción del ancho). AWAY se espeja.
FORMATION: list[tuple[float, float]] = [
    (0.25, 0.50),   # el más defensivo, al centro
    (0.40, 0.30),   # adelantado, banda superior
    (0.40, 0.70),   # adelantado, banda inferior
]
PLAYERS_PER_TEAM = 3

@dataclass(frozen=True, slots=True)
class PlayerSpec:
    id: int
    speed: float
    control: float
    strength: float
    power: float
    agility: float

    def __post_init__(self) -> None:
        values = [getattr(self, n) for n in ATTR_NAMES]
        for name, v in zip(ATTR_NAMES, values):
            if not ATTR_MIN <= v <= ATTR_MAX:
                raise ValueError(
                    f"{name}={v} fuera de rango [{ATTR_MIN}, {ATTR_MAX}]"
                )
        if sum(values) != ATTR_TOTAL:
            raise ValueError(
                f"Los atributos deben sumar {ATTR_TOTAL}, suman {sum(values)}"
            )
    
def kickoff_position(field: FieldConfig, team: Team, slot: int) -> Vec2: #donde se para un jugador
    fx, fy = FORMATION[slot]
    x = fx * field.length if team == Team.HOME else (1 - fx) * field.length
    return Vec2(x, fy * field.width)

def reset_to_kickoff(state: MatchState, field: FieldConfig) -> None: #Jugadores a su posición inicial, pelota al centro y sin dueño.
    slot_of: dict[Team, int] = {Team.HOME: 0, Team.AWAY: 0}
    for p in state.players:
        p.pos = kickoff_position(field, p.team, slot_of[p.team])
        p.vel = Vec2()
        slot_of[p.team] += 1
    state.ball.pos = field.center
    state.ball.vel = Vec2()
    state.ball.owner_id = None
    
def create_initial_state(
    field: FieldConfig,
    home: list[PlayerSpec],
    away: list[PlayerSpec],
) -> MatchState:
    if len(home) != PLAYERS_PER_TEAM or len(away) != PLAYERS_PER_TEAM:
        raise ValueError(f"Cada equipo necesita {PLAYERS_PER_TEAM} titulares") #comprueba que haya 3 jugadores por equipo, tal vez inecesario o la comprobacion deberia estar en otro lado

    players = [
        PlayerState(
            id=s.id, team=team, pos=Vec2(),
            speed=s.speed, control=s.control, strength=s.strength,
            power=s.power, agility=s.agility,
        )
        for team, specs in ((Team.HOME, home), (Team.AWAY, away))
        for s in specs
    ]
    state = MatchState(players=players, ball=BallState(pos=field.center))
    reset_to_kickoff(state, field)
    return state