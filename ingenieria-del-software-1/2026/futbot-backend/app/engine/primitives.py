import math
from dataclasses import dataclass
from typing import Dict, Optional, List

from app.schemas.coord import Coord
from app.core.config import settings
from app.models.player import PACSS_MAXIMO, PACSS_MINIMO

# Dimensiones oficiales del campo (Centrado en (0,0))
FIELD_WIDTH = 100.0
FIELD_HEIGHT = 60.0
HALF_WIDTH = FIELD_WIDTH / 2.0 # 50.0
HALF_HEIGHT = FIELD_HEIGHT / 2.0 # 30.0

PLAYER_MIN_SPEED = 4.0 # unidades por segundo a speed=20
PLAYER_MAX_SPEED = 9.0 # unidades por segundo a speed=100

BALL_MIN_POWER = 10.0 # unidades por segundo a power=20
BALL_MAX_POWER = 25.0 # unidades por segundo a power=100


@dataclass(slots=True)
class PlayerState:
    club_id: str
    position: Coord
    own_goal: Coord
    enemy_goal: Coord
    speed: int
    power: int
    control: int
    is_on_field: bool
    behavior_id: str


class MatchEngine:
    """
    Modulo de simulacion en memoria para resolucion de primitivas.
    """
    def __init__(self, players_data: Dict[str, PlayerState], ball_pos: Coord):
        self._players = players_data
        self._ball_pos = Coord(x=ball_pos.x, y=ball_pos.y)
        self._ball_velocity: Optional[Coord] = None # vector (vx, vy) por tick
        self._ball_target: Optional[Coord] = None
        self._ball_possessor_id: Optional[str] = None
        self._errors: Dict[str, List[str]] = {}
        self._update_possession_state()

    
    def _distance(self, c1:Coord, c2:Coord) -> float:
        """Funcion auxiliar para calcular distancia euclidiana"""
        return math.hypot(c1.x - c2.x, c1.y - c2.y)

    def _step_towards(self, origin: Coord, target: Coord, max_step: float) -> Coord:
        """
        Funcion auxiliar para calcular el nuevo punto hacia un objetivo limitado por el paso maximo.
        """
        dist = self._distance(origin, target)
        if dist < max_step or dist == 0:
            return Coord(x=target.x, y=target.y)
        
        ratio = max_step / dist
        return Coord(
                x=origin.x + (target.x - origin.x) * ratio,
                y=origin.y + (target.y - origin.y) * ratio,
        )

    
    def _max_step_speed(self, speed_stat: int) -> float:
        """
        Convierte la nota de speed (20-100) a distancia maxima alcanzable en 1 tick.
        """
        clamped_speed = max(PACSS_MINIMO, min(PACSS_MAXIMO, speed_stat))
        ratio = (clamped_speed - PACSS_MINIMO) / (PACSS_MAXIMO - PACSS_MINIMO)
        per_second = PLAYER_MIN_SPEED + ratio * (PLAYER_MAX_SPEED - PLAYER_MIN_SPEED)
        return per_second / settings.match_tick_rate

    
    def _max_step_power(self, power_stat: int, pass_ratio: float = 1.0) -> float:
        """
        Convierte la nota de power (20-100) a la velocidad/desplazamiento del balon en 1 tick.
        """
        clamped_power = max(PACSS_MINIMO, min(PACSS_MAXIMO, power_stat))
        ratio = (clamped_power - PACSS_MINIMO) / (PACSS_MAXIMO - PACSS_MINIMO)
        per_second = BALL_MIN_POWER + ratio * (BALL_MAX_POWER - BALL_MIN_POWER)
        return (per_second * pass_ratio) / settings.match_tick_rate


    def _control_radius(self, control_stat: int) -> float:
        """
        Funcion auxiliar para calcular el radio de control.
        """
        ratio = (control_stat - PACSS_MINIMO) / (PACSS_MAXIMO - PACSS_MINIMO)
        return 1.0 + ratio * 2.0

    
    def _update_possession_state(self) -> None:
        """
        Asigna la posesion al jugador mas cercano dentro de su radio de control.
        """
        if self._ball_velocity is not None:
            self._ball_possessor_id = None
            return
        
        candidates = [
            (p_id, self._distance(p.position, self._ball_pos))
            for p_id, p in self._players.items()
            if p.is_on_field
            and self._distance(p.position, self._ball_pos) <= self._control_radius(p.control)
        ]
        self._ball_possessor_id = min(candidates, key=lambda c: c[1])[0] if candidates else None


    def advance_ball(self) -> None:
        """
        Avanza la pelota un tick en la direccion de su velocidad si fue pateada.
        """
        if self._ball_target is None or self._ball_velocity is None:
            return

        max_step = math.hypot(self._ball_velocity.x, self._ball_velocity.y)
        self._ball_pos = self._step_towards(self._ball_pos, self._ball_target, max_step)

        # si llego al objetivo, detiene la pelota
        if self._ball_pos == self._ball_target:
            self._ball_velocity = None
            self._ball_target = None

        self._update_possession_state()


    #--------------Acciones------------------
    
    def apply_pass(self, player_id: str,target: Coord) -> None:
        if not self.is_inside_field(target):
            self.register_error(player_id, "Coordenada fuera de limites de pase")
            return


        if not self.player_has_ball(player_id):
            self.register_error(player_id, "El jugador intento pasar sin tener la pelota.")
            return
        
        player = self._players[player_id]
        step_speed = self._max_step_power(player.power, pass_ratio=0.7) # pase proporcional 70%

        dist = self._distance(self._ball_pos, target)

        if  dist == 0:
            return
            
        vx = ((target.x - self._ball_pos.x) / dist) * step_speed
        vy = ((target.y - self._ball_pos.y) / dist) * step_speed
        self._ball_velocity = Coord(x=vx, y=vy)
        self._ball_target = Coord(x=target.x, y=target.y)
        self._ball_possessor_id = None

    
    def apply_shot(self, player_id: str, target: Coord) -> None:
        if not self.is_inside_field(target):
            self.register_error(player_id, "Coordenada fuera de límites para tiro")
            return

        if not self.player_has_ball(player_id):
            self.register_error(player_id, "El jugador intento rematar sin tener la pelota.")
            return

        player = self._players[player_id]
        step_speed = self._max_step_power(player.power, pass_ratio=1.0)  # Máxima potencia

        dist = self._distance(self._ball_pos, target)

        if  dist == 0:
            return
        
        vx = ((target.x - self._ball_pos.x) / dist) * step_speed
        vy = ((target.y - self._ball_pos.y) / dist) * step_speed
        self._ball_velocity = Coord(x=vx, y=vy)
        self._ball_target = Coord(x=target.x, y=target.y)
        self._ball_possessor_id = None
        self.advance_ball()

    
    def apply_movement(self, player_id: str, target: Coord) -> None:
        if not self.is_inside_field(target):
            self.register_error(player_id, "Coordenada fuera de límites para movimiento")
            return

        player = self._players[player_id]
        max_step = self._max_step_speed(player.speed)
        has_ball = (self._ball_possessor_id == player_id)

        player.position = self._step_towards(player.position, target, max_step)

        # si el jugador tiene pelota, esta se traslada con el
        if has_ball:
            self._ball_pos = Coord(x=player.position.x, y=player.position.y)

        self._update_possession_state()


    #-------------------Consultas----------------------------


    def ball_position(self) -> Coord:
        """
        Devuelve coordenadas en tiempo real de la pelota.
        """
        return Coord(x=self._ball_pos.x, y=self._ball_pos.y)

    
    def nearest_teammate_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas de aliado mas cercano al jugador excluyendose a si mismo.
        """
        me = self._players[player_id]

        allies = [
            p for p_id, p in self._players.items()
            if p_id != player_id
            and p.club_id == me.club_id
            and p.is_on_field
        ]
        if not allies:
            return Coord(x=me.position.x, y=me.position.y)

        closest_ally = min(allies, key=lambda p: self._distance(me.position, p.position))
        return Coord(x=closest_ally.position.x, y=closest_ally.position.y)

    
    def nearest_opponent_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas de enemigo mas cercano al jugador.
        """
        me = self._players[player_id]
    
        enemies = [
            p for p in self._players.values()
            if p.club_id != me.club_id
            and p.is_on_field
        ]
        if not enemies:
            return Coord(x=me.position.x, y=me.position.y)

        closest_enemy = min(enemies, key=lambda p: self._distance(me.position, p.position)
        )
        return Coord(x=closest_enemy.position.x, y=closest_enemy.position.y)

    def own_goal_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas de arco aliado.
        """
        og = self._players[player_id].own_goal
        return Coord(x=og.x, y=og.y)
    
    
    def opponent_goal_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas de arco enemigo.
        """
        eg = self._players[player_id].enemy_goal
        return Coord(x=eg.x, y=eg.y)

    
    def player_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas del jugador.
        """
        pos = self._players[player_id].position
        return Coord(x=pos.x, y=pos.y)
    

    def player_has_ball(self, player_id: str) -> bool:
        """
        Devuelve True si el jugador es poseedor de la pelota.
        """
        return self._ball_possessor_id == player_id
    
        
    def team_has_ball(self, player_id: str) -> bool:
        """
        Devuelve True si equipo del jugador posee la pelota.
        """
        if self._ball_possessor_id is None:
            return False

        my_club = self._players[player_id].club_id
        possessor_club = self._players[self._ball_possessor_id].club_id
        return my_club == possessor_club

#-------------------------Precondiciones y metadatos-----------------------

    def is_inside_field(self, coord:Coord) -> bool:
        return -HALF_WIDTH <= coord.x <= HALF_WIDTH and -HALF_HEIGHT <= coord.y <= HALF_HEIGHT


    def player_is_on_field(self, player_id: str) -> bool:
        return self._players[player_id].is_on_field

    def assigned_behavior(self, player_id: str) -> str:
        return self._players[player_id].behavior_id

    def register_error(self, player_id: str, message: str) -> None:
        if player_id not in self._errors:
            self._errors[player_id] = []
        self._errors[player_id].append(message)