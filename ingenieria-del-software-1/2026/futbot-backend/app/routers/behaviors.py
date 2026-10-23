import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.schemas.behaviors import BehaviorRead
from app.services.behavior_services import get_all_behavior


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["behaviors"])

@router.get(
        "/behaviors", 
        response_model=list[BehaviorRead],
        status_code=status.HTTP_200_OK)

def get_behaviors(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> list[BehaviorRead]:
    try: 
        club_id = current_user.club.id
        return get_all_behavior(db, club_id)
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener comportamientos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener comportamientos"
        )