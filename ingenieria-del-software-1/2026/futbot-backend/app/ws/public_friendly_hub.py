import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.db.session import SessionLocal
from app.schemas.friendly_room import PublicFriendlyRoomResponse
from app.services.friendly_service import FriendlyService

logger = logging.getLogger(__name__)

CONEXION_CERRADA = (WebSocketDisconnect, RuntimeError)


def load_rooms() -> list[PublicFriendlyRoomResponse]:
    """Todas las salas públicas en espera, leídas con una sesión propia (el canal vive más que un request)."""
    with SessionLocal() as db:
        return FriendlyService(db).list_public_rooms()


class PublicFriendlyHub:
    """Conexiones suscriptas al listado de amistosos públicos, cada una con el club del usuario."""

    def __init__(self):
        self.clubs: dict[WebSocket, str] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        """Guarda el loop del servidor, para poder avisar desde hilos y código síncrono."""
        self.loop = loop

    def add(self, websocket: WebSocket, club_id: str) -> None:
        self.clubs[websocket] = club_id

    def remove(self, websocket: WebSocket) -> None:
        self.clubs.pop(websocket, None)

    async def send_list(self, websocket: WebSocket, rooms: list[PublicFriendlyRoomResponse] | None = None) -> None:
        """Envía a una conexión el listado, sin las salas de su propio club."""
        if rooms is None:
            rooms = load_rooms()
        club_id = self.clubs.get(websocket)
        await websocket.send_json({
            "type": "rooms",
            "rooms": [
                room.model_dump(mode="json", by_alias=True)      # mode="json": las fechas salen como texto
                for room in rooms if room.home_club != club_id
            ],
        })

    async def broadcast(self) -> None:
        """Avisa que las salas cambiaron: cada suscripto recibe su listado actualizado."""
        if not self.clubs:
            return
        rooms = load_rooms()                         # una sola consulta para todos
        fallo = None
        for websocket in list(self.clubs):
            try:
                await self.send_list(websocket, rooms)
            except CONEXION_CERRADA:                        # conexión cerrada o rota: se da de baja
                self.remove(websocket)
            except Exception as error:
                fallo = fallo or error
        if fallo is not None:
            raise fallo

    def notify_changed(self) -> None:
        """Pide un aviso desde código síncrono. No hace nada si nadie mira el listado."""
        loop = self.loop
        if loop is None or loop.is_closed() or not self.clubs:
            return
        future = asyncio.run_coroutine_threadsafe(self.broadcast(), loop)
        future.add_done_callback(self._log_failure)

    @staticmethod
    def _log_failure(future) -> None:
        if not future.cancelled() and future.exception() is not None:
            logger.warning("No se pudo avisar el cambio de amistosos", exc_info=future.exception())


public_friendly_hub = PublicFriendlyHub()