import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


from app.db.session import get_db
from app.models.user import User
from app.models.club import Club
from app.core.dependencies import get_current_user, get_current_club

from app.schemas.behaviors import BehaviorRead, BehaviorCreate, BehaviorUpdate
from app.services.behavior_services import get_all_behavior, erase_behavior_from_club
from app.services import behavior_services
from app.schemas.behavior_simulation import SimulationTicketCreate, SimulationTicketRead
from app.services.behavior_simulation import get_simulation_resources
from app.behaviors.validator import BehaviorValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["behaviors"])

# Diccionario para almacenar tickets de simulación de comportamiento
_ws_tickets: dict[str, dict] = {}

@router.get(
        "/behaviors", 
        response_model=list[BehaviorRead],
        status_code=status.HTTP_200_OK)

def get_behaviors(
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db)
) -> list[BehaviorRead]:
    try: 
        return behavior_services.get_all_behavior(db, club.id)
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener comportamientos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener comportamientos"
        )

@router.post(
    "/behaviors/simulate",
    status_code=status.HTTP_201_CREATED,
    response_model=SimulationTicketRead,
)
def create_simulation_ticket(
    request_data: SimulationTicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crea un ticket para la simulación de comportamiento y lo devuelve al front.
    El front debe usar este ticket para conectarse al websocket de simulación.
    """
    
    try:
        # Verifico que el jugador y el comportamiento existan
        player, behavior = get_simulation_resources(
            db=db, 
            player_id=request_data.player_id,
            behavior_id=request_data.behavior_id, 
            club_id=current_user.club.id
        )
        ticket = str(uuid.uuid4())
        _ws_tickets[ticket] = {
            "user_id": current_user.id,
            "player_id": request_data.player_id,
            "behavior_id": request_data.behavior_id,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)  # El ticket expira en 5 minutos
        }

        return {"ticket": ticket}
    except ValueError as error:
        logger.warning(f"Error al crear ticket de simulación: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        ) from error
    except Exception as e:
        logger.error(f"Error al crear ticket de simulación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear ticket de simulación"
        )

@router.delete(
    "/behaviors/{behavior_id}",
    status_code=status.HTTP_204_NO_CONTENT
    )
def erase_behavior(
    behavior_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        club_id = current_user.club.id
        erase_behavior_from_club(db, club_id, behavior_id)
        return
    except HTTPException as he:
        raise he
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error al eliminar comportamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al eliminar comportamiento."
        )
@router.get(
        "/behaviors/{behavior_id}",
        response_model=BehaviorRead,
        status_code=status.HTTP_200_OK)
def get_behavior(
    behavior_id: str,
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db)
) -> BehaviorRead:
    try:
        behavior = behavior_services.get_behavior_by_id(db, behavior_id, club.id)
        if not behavior:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comportamiento no encontrado"
            )
        return behavior
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener comportamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener comportamiento"
        )

@router.post(
        "/behaviors", 
        response_model=BehaviorRead,
        status_code=status.HTTP_201_CREATED)

def create_behavior(
    data: BehaviorCreate,
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db)
) -> BehaviorRead:
    try:
        new_behavior = behavior_services.create_behavior(db, data, club.id)
        return new_behavior
    except BehaviorValidationError as error:
        logger.warning(f"Error al crear comportamiento: {error}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    except ValueError as error:
        logger.warning(f"Error al crear comportamiento: {error}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    
    except SQLAlchemyError as e:
        logger.error(f"Error al crear comportamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear comportamiento"
        )

@router.put(
        "/behaviors/{behavior_id}", 
        response_model=BehaviorRead,
        status_code=status.HTTP_200_OK)
def update_behavior(
    behavior_id: str,
    data: BehaviorUpdate,
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db)
) -> BehaviorRead:
    try:
        updated_behavior = behavior_services.update_behavior(db, behavior_id, data, club.id)
        return updated_behavior
    except BehaviorValidationError as error:
        logger.warning(f"Error al actualizar comportamiento: {error}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    except SQLAlchemyError as e:
        logger.error(f"Error al actualizar comportamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar comportamiento"
        )
