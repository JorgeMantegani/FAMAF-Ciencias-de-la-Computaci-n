import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.player import PlayerCreate, PlayerResponse
from app.services.exceptions_player import AppException
from app.services.player_service import create_player, get_all_players

router = APIRouter(prefix="/api", tags=["create player"])

logger = logging.getLogger(__name__)


# Ticket: BE [BE] Endpoint Crear Jugador de Club
@router.post("/players", status_code=201, response_model=PlayerResponse)
def create_player_endpoint(
    player_data: PlayerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        player = create_player(db, current_user.club.id, player_data)
        return player

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/players", status_code=200)
def get_players_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[PlayerResponse]:
    try:
        club_id= current_user.club.id
        return get_all_players(db, club_id)
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener jugadores: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener jugadores"
        )
