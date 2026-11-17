from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.room import Room, ROOM_STATUS_IN_PROGRESS
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.squad_entry import SquadEntry, ROLE_STARTER, ROLE_SUBSTITUTE
from app.schemas.league import LineupUpdateRequest

def update_lineup_service(
    db: Session, 
    league_id: str, 
    payload:LineupUpdateRequest,
    user
):
    room = db.get(Room, league_id)
    if room is None:
        raise HTTPException(status_code=404, detail="La liga no existe")

    if room.status != ROOM_STATUS_IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail="La liga no está en curso",
        )

    club = db.scalar(select(Club).where(Club.user_id == user.id))
    if club is None:
        raise HTTPException(status_code=403, detail="El usuario no posee un club")

    enrolled = db.scalar(
        select(Enrollment).where(
            Enrollment.room_id == league_id,
            Enrollment.club_id == club.id,
        )
    )
    if enrolled is None:
        raise HTTPException(
            status_code=403,
            detail="El club no participa en esta liga",
        )

    if len(payload.starters) != 3 or len(payload.substitutes) != 3:
        raise HTTPException(
            status_code=400,
            detail="La alineación debe tener exactamente 3 titulares y 3 suplentes",
        )
    
    all_ids = payload.starters + payload.substitutes

    if len(set(all_ids)) != 6:
        raise HTTPException(
            status_code=400,
            detail="Los jugadores no pueden repetirse",
        )

    owned_count = db.scalar(
        select(func.count())
        .select_from(Player)
        .where(
            Player.id.in_(all_ids),
            Player.club_id == club.id,
            Player.deleted_at.is_(None),
        )
    )

    if owned_count != 6:
        raise HTTPException(
            status_code=403,
            detail="Uno o más jugadores no pertenecen al club",
        )

    entries = db.scalars(
        select(SquadEntry)
        .join(Player, Player.id == SquadEntry.player_id)
        .where(
            SquadEntry.room_id == league_id,
            Player.club_id == club.id,
        )
    ).all()

    entries_by_player = {entry.player_id: entry for entry in entries}

    missing = set(all_ids) - entries_by_player.keys()
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Los jugadores deben pertenecer a la plantilla de la liga",
        )

    for player_id in payload.starters:
        entries_by_player[player_id].role = ROLE_STARTER

    for player_id in payload.substitutes:
        entries_by_player[player_id].role = ROLE_SUBSTITUTE

    db.commit()

    # Retornamos un diccionario con los datos, el router se encarga del response_model
    return {
        "message": "Alineación actualizada correctamente",
        "effectiveNextMatch": True,
        "starters": payload.starters,
        "substitutes": payload.substitutes,
    }