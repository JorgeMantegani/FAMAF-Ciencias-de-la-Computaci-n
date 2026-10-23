import math
from app.engine.state import Team
import random

from app.engine.field import FieldConfig
from app.engine.state import BallState, PlayerState, Vec2
from app.engine.constants import PLAYER_MAX_SPEED, ATTR_MIN, ATTR_MAX, CONTROL_RADIUS
from app.engine.action import Kick

# --- Balance ---
MIN_SPEED_MS = 3.0        # jugador con speed = 20
BALL_FRICTION = 0.4       # fracción de velocidad que conserva la pelota tras 1 s
BALL_RESTITUTION = 0.7    # velocidad que conserva al rebotar
BALL_STOP_SPEED = 0.3     # por debajo de esto (m/s) la pelota se detiene
KICK_MIN_SPEED = 15.0        # m/s con power = 20
KICK_MAX_SPEED = 35.0        # m/s con power = 100
PASS_SPEED_FACTOR = 0.8      # un pase sale al 80 % de la fuerza de un remate
PASS_DIST_FACTOR = -math.log(BALL_FRICTION) * 1.1 #la pelota recorre v0 / -ln(F) metros hasta frenar se usa un 10 % de margen para que el pase no se quede corto
MAX_CONTROL_SPEED = 20.0     # una pelota más rápida no se puede controlar
KICK_COOLDOWN_TICKS = 8      # ~0,5 s a 15 tps
OWNER_BONUS = 1.5            # ventaja de quien ya tiene la pelota en una disputa

def normalize_attr(value: float) -> float:
    """Pasa un atributo del rango [ATTR_MIN, ATTR_MAX] a [0, 1]."""
    v = min(max(value, ATTR_MIN), ATTR_MAX)
    return (v - ATTR_MIN) / (ATTR_MAX - ATTR_MIN)

def max_speed_ms(speed_attr: float) -> float:
    return MIN_SPEED_MS + normalize_attr(speed_attr) * (PLAYER_MAX_SPEED - MIN_SPEED_MS)

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def move_player(player: PlayerState, target: Vec2, dt: float, field: FieldConfig) -> None:
    step = (target - player.pos).clamp_length(max_speed_ms(player.speed) * dt)
    new_pos = player.pos + step
    new_pos = Vec2(
        _clamp(new_pos.x, 0.0, field.length),
        _clamp(new_pos.y, 0.0, field.width),
    )
    player.vel = (new_pos - player.pos) * (1.0 / dt)
    player.pos = new_pos
    
def step_ball(ball: BallState, dt: float, field: FieldConfig) -> None:
    """Integra la pelota libre: movimiento, rozamiento y rebotes."""
    # 1. Rozamiento exponencial (independiente del tick rate)
    vel = ball.vel * (BALL_FRICTION ** dt)
    if vel.length() < BALL_STOP_SPEED:
        vel = Vec2()
    # 2. Integración
    x = ball.pos.x + vel.x * dt
    y = ball.pos.y + vel.y * dt
    vx, vy = vel.x, vel.y
    # 3. Bandas laterales (y = 0 y y = width): siempre rebota
    if y < 0.0:
        y, vy = -y, -vy * BALL_RESTITUTION
    elif y > field.width:
        y, vy = 2 * field.width - y, -vy * BALL_RESTITUTION
    # 4. Líneas de meta (x = 0 y x = length): rebota solo fuera del arco
    y_min, y_max = field.goal_y_range
    in_goal_mouth = y_min <= y <= y_max
    if not in_goal_mouth:
        if x < 0.0:
            x, vx = -x, -vx * BALL_RESTITUTION
        elif x > field.length:
            x, vx = 2 * field.length - x, -vx * BALL_RESTITUTION

    ball.pos = Vec2(x, y)
    ball.vel = Vec2(vx, vy)
    #CASO BORDE A SOLUCIONAR: step_ball hace rebotar la pelota usando la y final. 
    #Si un tiro diagonal cruza la línea dentro del arco pero termina fuera de él rebota y no se detecta gol
    

def check_goal(prev: Vec2, new: Vec2, field: FieldConfig) -> Team | None:
    y_min, y_max = field.goal_y_range
    # (x de la línea, equipo que anota, ¿cruza en este sentido?)
    lines = (
        (field.length, Team.HOME, prev.x < field.length <= new.x),
        (0.0,          Team.AWAY, new.x <= 0.0 < prev.x),
    )
    for line_x, scorer, crossed in lines:
        if not crossed:
            continue
        t = (line_x - prev.x) / (new.x - prev.x)   # fracción del segmento donde cruza
        y_at_line = prev.y + t * (new.y - prev.y)
        if y_min <= y_at_line <= y_max:
            return scorer
    return None

def kick_speed(power_attr: float) -> float:
    return KICK_MIN_SPEED + normalize_attr(power_attr) * (KICK_MAX_SPEED - KICK_MIN_SPEED)

def apply_kick(ball: BallState, player: PlayerState, kick: Kick) -> bool: #Convierte un Kick en velocidad de la pelota. Devuelve False si no se pudo
    if ball.owner_id != player.id:          # revalida: la posesión pudo cambiar
        return False
    direction = kick.target - ball.pos
    dist = direction.length()
    if dist == 0:
        return False

    speed = kick_speed(player.power)
    if kick.kind == "pass":
        speed = min(speed * PASS_SPEED_FACTOR, dist * PASS_DIST_FACTOR)

    ball.vel = direction.normalized() * speed
    ball.owner_id = None
    ball.last_kicker_id = player.id
    ball.cooldown_ticks = KICK_COOLDOWN_TICKS
    return True

def _contest_weight(p: PlayerState) -> float:
    return 1.0 + normalize_attr(p.control) + normalize_attr(p.strength)

def resolve_possession(ball: BallState, players: list[PlayerState], rng: random.Random) -> None: #Decide quién controla la pelota. Si tiene dueño, la pelota lo sigue
    owner = next((p for p in players if p.id == ball.owner_id), None)
    if owner is not None:
        ball.pos = owner.pos#Sincroniza: el dueño siempre es candidato

    cooling = ball.cooldown_ticks > 0
    candidates = [
        p for p in players
        if (p.pos - ball.pos).length() <= CONTROL_RADIUS
        and not (cooling and p.id == ball.last_kicker_id)
    ]
    #Una pelota libre muy rápida pasa de largo; la que lleva alguien no cuenta
    free_and_fast = owner is None and ball.vel.length() > MAX_CONTROL_SPEED
    
    if candidates and not free_and_fast:
        weights = [
            _contest_weight(p) * (OWNER_BONUS if p is owner else 1.0)
            for p in candidates
        ]
        winner = rng.choices(candidates, weights=weights)[0]
        ball.owner_id = winner.id
        ball.pos = winner.pos
        ball.vel = Vec2()

    if cooling:
        ball.cooldown_ticks -= 1