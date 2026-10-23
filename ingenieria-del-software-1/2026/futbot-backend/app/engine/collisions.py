from __future__ import annotations

import math

from app.engine.state import PlayerState, Vec2


def _clamp_to_field(pos: Vec2, field) -> Vec2:
    return Vec2(min(max(pos.x, 0.0), field.length),
                min(max(pos.y, 0.0), field.width))


def resolve_player_collisions(
    players: list[PlayerState],
    field,
    radius: float,
    iterations: int = 2,
) -> None:
    """Separa en el lugar a los jugadores solapados (modifica `p.pos`)."""
    min_dist = 2.0 * radius

    for _ in range(iterations):
        moved = False
        for i in range(len(players)):
            a = players[i]
            for j in range(i + 1, len(players)):
                b = players[j]
                dx, dy = b.pos.x - a.pos.x, b.pos.y - a.pos.y
                dist = math.hypot(dx, dy)
                if dist >= min_dist:
                    continue

                # Exactamente superpuestos: normal arbitraria pero determinista.
                if dist < 1e-9:
                    nx, ny, dist = 1.0, 0.0, 0.0
                else:
                    nx, ny = dx / dist, dy / dist

                overlap = min_dist - dist
                total = a.strength + b.strength          # > 0 (ATTR_MIN = 20)
                push_a = overlap * b.strength / total    # el más fuerte se mueve menos
                push_b = overlap * a.strength / total
                a.pos = _clamp_to_field(Vec2(a.pos.x - nx * push_a, a.pos.y - ny * push_a), field)
                b.pos = _clamp_to_field(Vec2(b.pos.x + nx * push_b, b.pos.y + ny * push_b), field)
                moved = True
        if not moved:   # ya no queda ningún solape: no hace falta otra pasada
            break