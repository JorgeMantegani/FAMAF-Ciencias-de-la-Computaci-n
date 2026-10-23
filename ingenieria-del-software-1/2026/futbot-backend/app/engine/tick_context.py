from app.engine.action import NULL_ACTION, Action, Kick
from app.engine.field import FieldConfig
from app.engine.state import MatchState, Vec2
from app.schemas.coord import Coord


def _v(c: Coord) -> Vec2:
    return Vec2(c.x, c.y)


def _c(v: Vec2) -> Coord:
    return Coord(x=v.x, y=v.y)


class TickContext:
    def __init__(self, state: MatchState, field: FieldConfig,
                 behavior_ids: dict[str, str]) -> None:
        # Snapshot: Vec2 es inmutable, así que copiar las referencias basta.
        self._field = field
        self._pos = {p.id: p.pos for p in state.players}
        self._team = {p.id: p.team for p in state.players}
        self._ball = state.ball.pos
        self._owner = state.ball.owner_id
        self._behavior_ids = behavior_ids
        self._moves: dict[str, Vec2] = {}
        self._kicks: dict[str, Kick] = {}
        self.errors: list[tuple[str, str]] = []

    # --- Resultado para el motor ---
    def action_for(self, pid: str) -> Action:
        if pid not in self._moves and pid not in self._kicks:
            return NULL_ACTION
        return Action(self._moves.get(pid), self._kicks.get(pid))

    # --- Consultas (las que usa el bot) ---
    def ball_position(self): return _c(self._ball)
    def player_position(self, pid): return _c(self._pos[pid])
    def player_has_ball(self, pid): return self._owner == pid

    def team_has_ball(self, pid):
        return self._owner is not None and self._team[self._owner] == self._team[pid]

    def player_is_on_field(self, pid): return pid in self._pos

    def is_inside_field(self, position):
        return (0 <= position.x <= self._field.length
                and 0 <= position.y <= self._field.width)

    def own_goal_position(self, pid):
        return Coord(x=self._field.own_goal_x(self._team[pid]),
                     y=self._field.width / 2)

    def opponent_goal_position(self, pid):
        return Coord(x=self._field.goal_x(self._team[pid]),
                     y=self._field.width / 2)

    def _nearest(self, pid, same_team: bool):
        me, team = self._pos[pid], self._team[pid]
        others = [q for q in self._pos
                  if q != pid and (self._team[q] == team) == same_team]
        best = min(others, key=lambda q: (self._pos[q] - me).length())
        return _c(self._pos[best])

    def nearest_teammate_position(self, pid): return self._nearest(pid, True)
    def nearest_opponent_position(self, pid): return self._nearest(pid, False)

    # --- Acciones (solo registran la intención) ---
    def apply_movement(self, pid, destination): self._moves[pid] = _v(destination)
    def apply_pass(self, pid, destination): self._kicks[pid] = Kick("pass", _v(destination))
    def apply_shot(self, pid, destination): self._kicks[pid] = Kick("shot", _v(destination))

    def assigned_behavior(self, pid): return self._behavior_ids[pid]
    def register_error(self, pid, message): self.errors.append((pid, message))