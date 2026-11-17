import random
import secrets
import string
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.room import (
    Room,
    ROOM_TYPE_FRIENDLY,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_STATUS_READY_TO_START,
)

from app.models.club import Club
from app.schemas.friendly_room import (
    CreateFriendlyRoomRequest, FriendlyRoomResponse, RoomStatus,
    JoinFriendlyRoomRequest, JoinFriendlyRoomResponse, PublicFriendlyRoomResponse,
)

from app.models.enrollment import Enrollment
from app.models.squad_entry import (
    SquadEntry,
    ROLE_STARTER,
    ROLE_SUBSTITUTE,
)

from app.schemas.friendly_room import CreateFriendlyRoomRequest, FriendlyRoomResponse, RoomStatus, JoinFriendlyRoomRequest, JoinFriendlyRoomResponse
from app.services.squad_validator import validate_squad_selection

ROOM_UNAVAILABLE = {
    "detail": "La sala ya no está disponible.",
    "error_code": "ROOM_NOT_AVAILABLE",
}

def _room_unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=dict(ROOM_UNAVAILABLE))

class FriendlyService:
    def __init__(self, db: Session):
        self.db = db

    def create_room(self, club_id: str, request: CreateFriendlyRoomRequest) -> FriendlyRoomResponse:

        # Validaciones de negocio
        validate_squad_selection(self.db, club_id, request.starters, request.substitutes)



        # Crear sala con estado waiting_guest
        try:
            new_room = Room(
                type=ROOM_TYPE_FRIENDLY,
                min_clubs=2,
                max_clubs=2,
                match_duration_minutes=10,
                status=ROOM_STATUS_WAITING_GUEST,
                creator_club_id=club_id,
            )
            self.db.add(new_room)
            self.db.flush()
            room_id = new_room.id




            # Registrar participacion del club creador de sala
            enrollment = Enrollment(
                room_id=new_room.id,
                club_id=club_id
            )
            self.db.add(enrollment)




            # Registrat los titulares y suplentes en SquadEntry
            for selection in request.starters:
                squad_entry = SquadEntry(
                    room_id=new_room.id,
                    player_id=selection.player_id,
                    behavior_id=selection.behavior_id,
                    role=ROLE_STARTER
                )
                self.db.add(squad_entry)

            for selection in request.substitutes:
                squad_entry = SquadEntry(
                    room_id=new_room.id,
                    player_id=selection.player_id,
                    behavior_id=selection.behavior_id,
                    role=ROLE_SUBSTITUTE                                
                )
                self.db.add(squad_entry)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return FriendlyRoomResponse(
            room_id=new_room.id,
            status=RoomStatus.WAITING_GUEST.value,
            home_club=club_id
        )
    
    def join_room(self, club_id: str, room_id: str, request: JoinFriendlyRoomRequest) -> JoinFriendlyRoomResponse:
        room = self.db.query(Room).filter(Room.id == room_id).first()

        if room is None or room.type != ROOM_TYPE_FRIENDLY:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sala no encontrada"
            )

        if room.status != ROOM_STATUS_WAITING_GUEST:
            raise _room_unavailable()

        if room.creator_club_id == club_id:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="No podés unirte a tu propia sala.")

        validate_squad_selection(self.db, club_id, request.starters, request.substitutes)

        real_room_id = room.id
        try:
            claimed = (
                self.db.query(Room)
                .filter(Room.id == real_room_id, Room.status == ROOM_STATUS_WAITING_GUEST)
                .update({Room.status: ROOM_STATUS_READY_TO_START}, synchronize_session=False)
            )
            if claimed == 0:
                raise _room_unavailable()

            self.db.add(Enrollment(room_id=real_room_id, club_id=club_id))
            for role, selections in (
                (ROLE_STARTER, request.starters),
                (ROLE_SUBSTITUTE, request.substitutes),
            ):
                for s in selections:
                    self.db.add(SquadEntry(
                        room_id=real_room_id,
                        player_id=s.player_id,
                        behavior_id=s.behavior_id,
                        role=role,
                    ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return JoinFriendlyRoomResponse(
            room_id=real_room_id,
            status=RoomStatus.READY_TO_START.value,
            away_club=club_id,
        )

    def list_public_rooms(self, club_id: str | None = None) -> list[PublicFriendlyRoomResponse]:
        query = (
            self.db.query(Room, Club.name)
            .join(Club, Club.id == Room.creator_club_id)
            .filter(
                Room.type == ROOM_TYPE_FRIENDLY,               # las ligas comparten tabla y también arrancan en waiting_guest
                Room.status == ROOM_STATUS_WAITING_GUEST,      # ni iniciadas, ni canceladas, ni completas
            )
        )
        if club_id is not None:
            query = query.filter(Room.creator_club_id != club_id)   # para no mostrar las salas propias
        rows = query.order_by(Room.created_at.desc(), Room.id).all()
        return [
            PublicFriendlyRoomResponse(
                room_id=room.id,
                status=RoomStatus.WAITING_GUEST.value,
                home_club=room.creator_club_id,
                home_club_name=club_name,
                created_at=room.created_at,
            )
            for room, club_name in rows
        ]