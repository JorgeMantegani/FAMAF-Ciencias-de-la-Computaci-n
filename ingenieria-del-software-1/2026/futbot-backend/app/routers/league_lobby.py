from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.room import Room
from app.models.club import Club
from app.models.squad_entry import SquadEntry, ROLE_STARTER, ROLE_SUBSTITUTE, STARTER_COUNT, SUBSTITUTE_COUNT
from app.services.league_orchestrator import get_league_lobby_payload
from pydantic import BaseModel, Field
from app.schemas.league import LineupUpdateRequest, LineupUpdateResponse
from app.services.league_lobby_services import update_lineup_service

router = APIRouter(prefix="/api/leagues", tags=["league-lobby"])

class SquadMemberUpdate(BaseModel):
    player_id: str
    role: str = Field(..., pattern=f"^({ROLE_STARTER}|{ROLE_SUBSTITUTE})$")
    behavior_id: str

class SquadUpdateRequest(BaseModel):
    entries: list[SquadMemberUpdate]

@router.get("/{league_id}/live-lobby")
def get_live_lobby(league_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Obtengo el club del usuario
    club = db.scalar(
        select(Club).where(Club.user_id == user.id)
    )

    if club is None:
        raise HTTPException(
            status_code=403,
            detail="El usuario no posee un club",
        )
    
    payload = get_league_lobby_payload(db, league_id, club.id)
    if not payload:
        raise HTTPException(status_code=400, detail="La liga no existe o no está en progreso")
    return payload

@router.put("/{league_id}/squad", status_code=200)
def update_league_squad(
    league_id: str,
    payload: SquadUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Actualiza la alineacion."""
    room = db.get(Room, league_id)
    if not room:
        raise HTTPException(status_code=404, detail="La liga no existe")

    club = db.execute(
        select(Club).where(Club.user_id == user.id)
    ).scalar_one_or_none()

    if not club:
        raise HTTPException(status_code=403, detail="El usuario no posee un club asociado")

    starters = [e for e in payload.entries if e.role == ROLE_STARTER]
    substitutes = [e for e in payload.entries if e.role == ROLE_SUBSTITUTE]

    if len(starters) != STARTER_COUNT or len(substitutes) != SUBSTITUTE_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Se requieren exactamente {STARTER_COUNT} titulares y {SUBSTITUTE_COUNT} suplentes"
        )

    existing_entries = db.execute(
        select(SquadEntry).where(SquadEntry.room_id == league_id)
    ).scalars().all()

    existing_map = {entry.player_id: entry for entry in existing_entries}

    for entry_data in payload.entries:
        if entry_data.player_id in existing_map:
            # Modificación lógica directa sobre la entidad existente
            db_entry = existing_map[entry_data.player_id]
            db_entry.role = entry_data.role
            db_entry.behavior_id = entry_data.behavior_id
        else:
            # Registro de nuevos convocados
            new_entry = SquadEntry(
                room_id=league_id,
                player_id=entry_data.player_id,
                behavior_id=entry_data.behavior_id,
                role=entry_data.role
            )
            db.add(new_entry)

    db.commit()
    return {"status": "success", "message": "Plantilla actualizada correctamente"}

@router.put(
    "/{league_id}/lineup",
    response_model=LineupUpdateResponse,
    status_code=200,
)
def update_lineup(
    league_id: str,
    payload: LineupUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):

    result = update_lineup_service(db=db, league_id=league_id, payload=payload, user=user)
    
    return result