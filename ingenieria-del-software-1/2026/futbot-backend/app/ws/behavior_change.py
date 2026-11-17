"""Evento CHANGE_BEHAVIOR: valida el pedido, lo encola en el motor y responde por el socket."""

from fastapi import WebSocket
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.services.behavior_change_service import (
    behavior_belongs_to_club,
    compile_behavior,
    save_current_behavior,
)


class BehaviorChangeRejected(Exception):
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message


def parse_payload(payload) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise BehaviorChangeRejected("BEHAVIOR_CHANGE_INVALID_REQUEST", "El payload es inválido.")
    player_id, behavior_id = payload.get("playerId"), payload.get("behaviorId")
    if not isinstance(player_id, str) or not isinstance(behavior_id, str):
        raise BehaviorChangeRejected(
            "BEHAVIOR_CHANGE_INVALID_REQUEST", "playerId y behaviorId son obligatorios."
        )
    return player_id, behavior_id


def _behavior_is_available(bind, behavior_id: str, club_id: str) -> bool:
    with Session(bind) as db:
        return behavior_belongs_to_club(db, behavior_id, club_id)


def _compile_behavior(bind, behavior_id: str) -> bool:
    with Session(bind) as db:
        return compile_behavior(db, behavior_id)


def _save_behavior(bind, match_id: str, player_id: str, behavior_id: str) -> None:
    with Session(bind) as db:
        save_current_behavior(db, match_id, player_id, behavior_id)


async def handle_change_behavior(
    socket: WebSocket, bind, engine, club_id: str, payload, match_id: str
) -> None:
    try:
        player_id, behavior_id = parse_payload(payload)
        if engine is None:
            raise BehaviorChangeRejected(
                "BEHAVIOR_CHANGE_MATCH_NOT_RUNNING", "El partido no está en curso."
            )
        if not await run_in_threadpool(_behavior_is_available, bind, behavior_id, club_id):
            raise BehaviorChangeRejected(
                "BEHAVIOR_CHANGE_BEHAVIOR_UNAVAILABLE",
                "El comportamiento no existe o no está disponible.",
            )
        if not await run_in_threadpool(_compile_behavior, bind, behavior_id):
            raise BehaviorChangeRejected(
                "BEHAVIOR_CHANGE_BEHAVIOR_INVALID", "El comportamiento no se pudo cargar."
            )
        try:
            engine.request_behavior_change(club_id, player_id, behavior_id)
        except ValueError as error:
            raise BehaviorChangeRejected("BEHAVIOR_CHANGE_INVALID_PLAYER", str(error))
        await run_in_threadpool(_save_behavior, bind, match_id, player_id, behavior_id)
    except BehaviorChangeRejected as error:
        await socket.send_json({
            "type": "error",
            "ok": False,
            "error_code": error.error_code,
            "message": error.message,
        })
        return
    await socket.send_json(
        {"event": "BEHAVIOR_CHANGED", "payload": {"playerId": player_id, "behaviorId": behavior_id}}
    )
