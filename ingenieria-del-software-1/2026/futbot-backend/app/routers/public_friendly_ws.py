import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.dependencies import get_user_from_token
from app.db.session import get_db
from app.ws.public_friendly_hub import public_friendly_hub

router = APIRouter()

AUTH_TIMEOUT_SECONDS = 5
CLOSE_UNAUTHORIZED = 4401


@router.websocket("/ws/friendly-rooms/public")
async def public_friendly_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()

    # El navegador no puede mandar headers en un WebSocket: el token viaja en el primer mensaje
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, ValueError, KeyError):
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    user = None
    if isinstance(first, dict) and first.get("type") == "auth":
        user = get_user_from_token(db, first.get("token"))
    club_id = str(user.club.id) if user is not None and user.club is not None else None   # antes de cerrar la sesión
    db.close()                                       # no retener la sesión durante toda la conexión
    if club_id is None:                              # token inválido, o usuario sin club
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    public_friendly_hub.add(websocket, club_id)
    try:
        await public_friendly_hub.send_list(websocket)    # listado inicial
        while True:
            await websocket.receive_text()                # el cliente no envía nada más: solo detecta la desconexión
    except WebSocketDisconnect:
        pass
    finally:
        public_friendly_hub.remove(websocket)