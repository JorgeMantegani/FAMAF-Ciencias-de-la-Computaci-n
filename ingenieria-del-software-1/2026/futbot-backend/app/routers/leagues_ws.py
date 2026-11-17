import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.dependencies import get_user_from_token
from app.db.session import get_db
from app.ws.leagues_hub import leagues_hub

router = APIRouter()

AUTH_TIMEOUT_SECONDS = 5
CLOSE_UNAUTHORIZED = 4401
MAX_NAME_LENGTH = 80


@router.websocket("/ws/leagues")
async def leagues_ws(websocket: WebSocket, db: Session = Depends(get_db)):
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
    db.close()                                       # no retener la sesión durante toda la conexión
    if user is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    leagues_hub.add(websocket)
    try:
        await leagues_hub.send_list(websocket)       # listado inicial, sin filtro
        while True:
            try:
                message = await websocket.receive_json()
            except ValueError:
                await websocket.send_json({"type": "error", "detail": "Mensaje inválido."})
                continue
            if not isinstance(message, dict) or message.get("type") != "search":
                continue                             # cualquier otro mensaje se ignora
            name = message.get("name", "")
            if not isinstance(name, str) or len(name.strip()) > MAX_NAME_LENGTH:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"El filtro debe ser un texto de hasta {MAX_NAME_LENGTH} caracteres.",
                })
                continue
            leagues_hub.set_filter(websocket, name.strip())
            await leagues_hub.send_list(websocket)
    except WebSocketDisconnect:
        pass
    finally:
        leagues_hub.remove(websocket)