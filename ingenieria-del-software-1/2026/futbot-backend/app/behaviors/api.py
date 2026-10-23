from app.behaviors.interfaces import IMatchEngine
from app.schemas.coord import Coord


class JugadorAPI:
    """El objeto `jugador` que recibe la funcion `comportamiento(jugador)`
    """

    def __init__(self, player_id: str, engine: IMatchEngine) -> None:
        self._player_id = player_id
        self._engine = engine

    # --- Consultas ---
    def encontrar_pelota(self) -> Coord:
        return self._engine.ball_position()

    def encontrar_aliado(self) -> Coord:
        return self._engine.nearest_teammate_position(self._player_id)

    def encontrar_enemigo(self) -> Coord:
        return self._engine.nearest_opponent_position(self._player_id)

    def encontrar_arco_aliado(self) -> Coord:
        return self._engine.own_goal_position(self._player_id)

    def encontrar_arco_enemigo(self) -> Coord:
        return self._engine.opponent_goal_position(self._player_id)

    def encontrar_mis_coordenadas(self) -> Coord:
        return self._engine.player_position(self._player_id)

    def tengo_pelota(self) -> bool:
        return self._engine.player_has_ball(self._player_id)

    def club_tiene_pelota(self) -> bool:
        return self._engine.team_has_ball(self._player_id)

    # --- Acciones ---
    def pasar(self, destino: Coord) -> None:
        if not self._engine.is_inside_field(destino):
            return
        if not self._engine.player_has_ball(self._player_id):
            return
        self._engine.apply_pass(self._player_id, destino)

    def patear_pelota(self, destino: Coord) -> None:
        if not self._engine.is_inside_field(destino):
            return
        if not self._engine.player_has_ball(self._player_id):
            return
        self._engine.apply_shot(self._player_id, destino)

    def correr(self, destino: Coord) -> None:
        if not self._engine.is_inside_field(destino):
            return
        if not self._engine.player_is_on_field(self._player_id):
            return
        self._engine.apply_movement(self._player_id, destino)