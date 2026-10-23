from dataclasses import dataclass
from typing import Literal

from app.engine.state import Vec2


@dataclass(frozen=True, slots=True)
class Kick:
    kind: Literal["pass", "shot"]
    target: Vec2


@dataclass(frozen=True, slots=True)
class Action:
    move_to: Vec2 | None = None
    kick: Kick | None = None


NULL_ACTION = Action()   # inmóvil y sin remate