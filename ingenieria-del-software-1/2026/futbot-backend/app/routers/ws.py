from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enrollment import Enrollment
from app.models.room import Room
from app.ws.manager import room_manager as manager


router = APIRouter()


@router.websocket("/ws/friendly/{room_id}")
async def friendly_ws(
    websocket: WebSocket,
    room_id: str,
    club_id: str,
    db: Session = Depends(get_db),
):
    await websocket.accept()

    room_exists = db.query(Room).filter(Room.id == room_id).first() is not None
    enrolled = room_exists and db.query(Enrollment).filter(
        Enrollment.room_id == room_id,
        Enrollment.club_id == club_id,
    ).first() is not None

    db.close()

    if not room_exists:
        await websocket.close(code=4404)
        return

    if not enrolled:
        await websocket.close(code=4403)
        return

    await manager.connect(room_id, club_id, websocket)
    await manager.broadcast(room_id, {
        "type": "club_connected",
        "club_id": club_id,
    })

    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager.disconnect(room_id, club_id)
        await manager.broadcast(room_id, {
            "type": "club_disconnected",
            "club_id": club_id,
        })