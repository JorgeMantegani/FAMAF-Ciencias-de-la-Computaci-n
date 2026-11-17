"""Gestión de suscripciones de partidos y conexiones de salas amistosas."""

import asyncio
from dataclasses import dataclass
from threading import RLock

from fastapi import WebSocket

from sqlalchemy.orm import Session

from app.schemas.match_state import MatchState
from app.models.room import Room, ROOM_STATUS_FINISHED, ROOM_STATUS_CANCELLED
from app.models.enrollment import Enrollment


@dataclass(eq=False)
class Subscription:
    match_id: str
    session_id: str
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue
    event_queue: asyncio.Queue
    active: bool = True
    revoked: bool = False

    def deliver(self, message: dict) -> None:
        if not self.active or (self.revoked and message["type"] != "revoked"):
            return

        # Cada mensaje es un snapshot completo: si el cliente va lento,
        # conserva el más reciente sin acumular ticks.
        if self.queue.full():
            self.queue.get_nowait()

        self.queue.put_nowait(message)

    def deliver_event(self, message: dict) -> None:
        if self.active and not self.revoked:
            self.event_queue.put_nowait(message)


class ConnectionManager:
    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()
        self._lock = RLock()

    def subscribe(self, match_id: str, session_id: str) -> Subscription:
        subscription = Subscription(
            match_id=match_id,
            session_id=session_id,
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=1),
            event_queue=asyncio.Queue(),
        )
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            subscription.active = False
            self._subscriptions.discard(subscription)

    def _notify(self, subscription: Subscription, message: dict) -> None:
        try:
            subscription.loop.call_soon_threadsafe(subscription.deliver, message)
        except RuntimeError:
            # El loop del cliente ya cerró.
            self.unsubscribe(subscription)

    def broadcast(self, state: MatchState) -> None:
        message = {
            "type": "state",
            "state": state.model_dump(mode="json"),
        }

        with self._lock:
            for subscription in tuple(self._subscriptions):
                if (
                    subscription.match_id == str(state.match_id)
                    and not subscription.revoked
                ):
                    self._notify(subscription, message)

    def broadcast_event(self, match_id: str, message: dict) -> None:
        with self._lock:
            for subscription in tuple(self._subscriptions):
                if subscription.match_id == str(match_id) and not subscription.revoked:
                    try:
                        subscription.loop.call_soon_threadsafe(
                            subscription.deliver_event, message
                        )
                    except RuntimeError:
                        self.unsubscribe(subscription)

    def revoke_session(self, session_id: str) -> None:
        with self._lock:
            for subscription in tuple(self._subscriptions):
                if subscription.session_id == session_id:
                    subscription.revoked = True
                    self._notify(subscription, {"type": "revoked"})


manager = ConnectionManager()


MAX_USERS = 2


class RoomConnectionManager:
    def __init__(self) -> None:
        # {room_id: {user_id: websocket}}
        self.rooms: dict[str, dict[str, WebSocket]] = {}

    def full_room(self, room_id: str, user_id: str) -> bool:
        users = self.rooms.get(room_id, {})
        return user_id not in users and len(users) >= MAX_USERS

    async def connect(
        self,
        room_id: str,
        user_id: str,
        ws: WebSocket,
    ) -> None:
        self.rooms.setdefault(room_id, {})[user_id] = ws

    def disconnect(self, room_id: str, user_id: str) -> None:
        self.rooms.get(room_id, {}).pop(user_id, None)

        if room_id in self.rooms and not self.rooms[room_id]:
            del self.rooms[room_id]

    async def send(self, ws: WebSocket, message: dict) -> None:
        await ws.send_json(message)

    async def broadcast(self, room_id: str, message: dict) -> None:
        for ws in list(self.rooms.get(room_id, {}).values()):
            await ws.send_json(message)


room_manager = RoomConnectionManager()

class LeagueRoomManager:
    def __init__(self) -> None:
        self.waiting_rooms: dict[str, dict[str, WebSocket]] = {}
        self.active_rooms: dict[str, dict[str, WebSocket]] = {}

    def get_rooms_user_count(self, league_id: str, is_active: bool = False) -> int:
        rooms = self.active_rooms if is_active else self.waiting_rooms
        return len(rooms.get(league_id, {}))

    async def connect_waiting(self, league_id: str, club_id: str, ws: WebSocket, max_clubs: int) -> bool:
        if league_id not in self.waiting_rooms:
            self.waiting_rooms[league_id] = {}

        if club_id not in self.waiting_rooms[league_id] and len(self.waiting_rooms[league_id]) >= max_clubs:
            return False

        self.waiting_rooms[league_id][club_id] = ws
        return True

    async def connect_active(self, league_id: str, club_id: str, ws: WebSocket) -> None:
        if league_id not in self.active_rooms:
            self.active_rooms[league_id] = {}
        self.active_rooms[league_id][club_id] = ws

    def disconnect_waiting(self, league_id: str, club_id: str):
        if league_id in self.waiting_rooms:
            self.waiting_rooms[league_id].pop(club_id, None)
            if not self.waiting_rooms[league_id]:
                del self.waiting_rooms[league_id]

    def disconnect_active(self, league_id: str, club_id: str) -> None:
        if league_id in self.active_rooms:
            self.active_rooms[league_id].pop(club_id, None)
            if not self.active_rooms[league_id]:
                del self.active_rooms[league_id]

    async def broadcast_waiting(self, league_id: str, message: dict, exclude_club_id: str = None):
        for club_id, ws in list(self.waiting_rooms.get(league_id, {}).items()):
            if club_id != exclude_club_id:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect_waiting(league_id, club_id)

    async def broadcast_active(self, league_id: str, message: dict, exclude_club_id: str = None):
        for club_id, ws in list(self.active_rooms.get(league_id, {}).items()):
            if club_id != exclude_club_id:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect_waiting(league_id, club_id)

league_manager= LeagueRoomManager()

class ActiveRoomsConnectionManager:
    def __init__(self) -> None:
        # Mapear user_id -> conjunto de websockets activos
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.setdefault(user_id, set()).add(ws)

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        if user_id in self.connections:
            self.connections[user_id].discard(ws)
            if not self.connections[user_id]:
                del self.connections[user_id]

    async def send_active_rooms(self, user_id: str, club_id: str, db: Session, ws: WebSocket) -> None:
        rooms = (
            db.query(Room)
            .join(Enrollment, Enrollment.room_id == Room.id)
            .filter(
                Enrollment.club_id == club_id,
                ~Room.status.in_([ROOM_STATUS_FINISHED, ROOM_STATUS_CANCELLED])
            )
            .all()
        )

        data = [
            {
                "id": r.id,
                "code": r.code,
                "type": r.type,
                "status": r.status
            }
            for r in rooms
        ]
        await ws.send_json(data)

    async def broadcast_to_user(self, user_id: str, club_id: str, db: Session) -> None:
        if user_id in self.connections:
            rooms = (
                db.query(Room)
                .join(Enrollment, Enrollment.room_id == Room.id)
                .filter(
                    Enrollment.club_id == club_id,
                    ~Room.status.in_([ROOM_STATUS_FINISHED, ROOM_STATUS_CANCELLED])
                )
                .all()
            )
            data = [
                {
                    "id": r.id,
                    "code": r.code,
                    "type": r.type,
                    "status": r.status
                }
                for r in rooms
            ]
            for ws in list(self.connections[user_id]):
                try:
                    await ws.send_json(data)
                except Exception:
                    self.disconnect(user_id, ws)
active_rooms_manager = ActiveRoomsConnectionManager()
