from dataclasses import dataclass
from app.engine.state import Team, Vec2


@dataclass(frozen=True, slots=True)
class FieldConfig:
    length: float = 105.0
    width: float = 68.0
    goal_width: float = 12   # ajustalo jugando

    @property
    def center(self) -> Vec2:
        return Vec2(self.length / 2, self.width / 2)

    @property
    def goal_y_range(self) -> tuple[float, float]:
        half = self.goal_width / 2
        return (self.width / 2 - half, self.width / 2 + half)

    def goal_x(self, team: Team) -> float:
        """Línea de meta que ATACA este equipo (HOME ataca hacia x=length)."""
        return self.length if team == Team.HOME else 0.0

    def own_goal_x(self, team: Team) -> float:
        """Línea de meta que DEFIENDE este equipo."""
        return 0.0 if team == Team.HOME else self.length