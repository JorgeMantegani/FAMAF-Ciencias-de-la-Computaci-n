import random
import secrets
import string
from fastapi import HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.models.room import (
    Room,
    ROOM_TYPE_FRIENDLY,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_STATUS_READY_TO_START,
)

from app.models.enrollment import Enrollment
from app.models.squad_entry import (
    SquadEntry,
    ROLE_STARTER,
    ROLE_SUBSTITUTE,
    STARTER_COUNT,
    SUBSTITUTE_COUNT,
)

from app.models.player import Player
from app.models.behavior import Behavior
from app.schemas.friendly_room import CreateFriendlyRoomRequest, FriendlyRoomResponse, RoomStatus, JoinFriendlyRoomRequest, JoinFriendlyRoomResponse

def generate_room_code(length: int = 6) -> str:
    """Genera un codigo alfanumerico unico para unirse a la sala de amistoso"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

class FriendlyService:
    def __init__(self, db: Session):
        self.db = db

    def validate_players_and_behaviors(self, club_id: str, request: CreateFriendlyRoomRequest | JoinFriendlyRoomRequest):
        
        # Validacion de numero de jugadores
        if len(request.starters) != STARTER_COUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Se requieren exactamente {STARTER_COUNT} jugadores titulares."
            )
        if len(request.substitutes) != SUBSTITUTE_COUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Se requieren exactamente {SUBSTITUTE_COUNT} jugadores suplentes."
            )

        all_selecctions = request.starters + request.substitutes
        player_ids = [s.player_id for s in all_selecctions]
        behavior_ids = [s.behavior_id for s in all_selecctions]




        # Checkeo de jugadores repetidos
        if len(set(player_ids)) != len(player_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede seleccionar el mismo jugador mas de una vez."
            )




        # Validacion de pertenencia de jugadores existentes en el club
        valid_players = (
            self.db.query(Player.name, Player.id)
            .filter(
                Player.name.in_(player_ids),
                Player.club_id == club_id,
                Player.deleted_at.is_(None)
            ).all()
        )
        valid_players_ids = {p.name: p.id for p in valid_players}
        
        if len(valid_players_ids) != len(player_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Al menos un jugador seleccionado no pertenece a tu club o no esta disponible."
            )

        for selection in all_selecctions:
            selection.player_id = valid_players_ids[selection.player_id]



        # Validacion de comportamientos pertenecen a club o son preprogramados
        valid_behaviors = (
            self.db.query(Behavior.id)
            .filter(
                Behavior.id.in_(behavior_ids),
                Behavior.deleted_at.is_(None),
                or_(
                    Behavior.club_id == club_id,
                    Behavior.is_preprogrammed.is_(True),
                    Behavior.club_id.is_(None)
                )
            )
            .all()
        )
        valid_behaviors_ids = {b.id for b in valid_behaviors}

        if len(valid_behaviors_ids) != len(set(behavior_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Al menos un comportamiento seleccionado es invalido o no pertenece a tu club."
            )


    def create_room(self, club_id: str, request: CreateFriendlyRoomRequest) -> FriendlyRoomResponse:
        
        # Validaciones de negocio
        self.validate_players_and_behaviors(club_id, request)



        # Generacion de codigo unico de sala
        room_code = generate_room_code()
        while self.db.query(Room).filter(Room.code == room_code).first() is not None:
            room_code = generate_room_code()




        # Crear sala con estado waiting_guest
        new_room = Room(
            type=ROOM_TYPE_FRIENDLY,
            min_clubs=2,
            max_clubs=2,
            match_duration_minutes=10,
            status=ROOM_STATUS_WAITING_GUEST,
            creator_club_id=club_id,
            code=room_code
        )
        self.db.add(new_room)
        self.db.flush()




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

        return FriendlyRoomResponse(
            room_id=new_room.id,
            room_code=room_code,
            status=RoomStatus.WAITING_GUEST.value,
            home_club=club_id
        )
    
    def join_room(self, club_id: str, room_id: str, request: JoinFriendlyRoomRequest) -> JoinFriendlyRoomResponse:
        room = self.db.query(Room).filter(Room.id == room_id).first()

        valid_code = (
            room is not None
            and room.code is not None
            and secrets.compare_digest(room.code, request.code.strip().upper())
        )
        if not valid_code or room.type != ROOM_TYPE_FRIENDLY:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sala no encontrada o codigo incorrecto"
            )

        if room.status != ROOM_STATUS_WAITING_GUEST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La sala esta completa o fue iniciada."
                )

        # verificar que el club tiene al menos 6 jugadores
        total_players = (
            self.db.query(func.count(Player.id))
            .filter(Player.club_id == club_id, Player.deleted_at.is_(None))
            .scalar()
        )
        if total_players < STARTER_COUNT + SUBSTITUTE_COUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Necesitas al menos {STARTER_COUNT + SUBSTITUTE_COUNT} jugadores creados para unirte.",
            )

        self.validate_players_and_behaviors(club_id, request)

        # Solo un invitado puede pasar de waiting_guest a ready_to_start
        reclaimed = (
            self.db.query(Room)
            .filter(Room.id == room.id, Room.status == ROOM_STATUS_WAITING_GUEST)
            .update({Room.status: ROOM_STATUS_READY_TO_START}, synchronize_session=False)
        )
        if reclaimed == 0:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La sala esta completa o fue iniciada."
                )

        self.db.add(Enrollment(room_id=room.id, club_id=club_id))
        for role, selections in (
            (ROLE_STARTER, request.starters),
            (ROLE_SUBSTITUTE, request.substitutes),
        ):
            for s in selections:
                self.db.add(SquadEntry(
                    room_id=room.id,
                    player_id=s.player_id,
                    behavior_id=s.behavior_id,
                    role=role,
                ))

        self.db.commit()

        return JoinFriendlyRoomResponse(
            room_id=room.id,
            status=RoomStatus.READY_TO_START.value,
            away_club=club_id,
        )