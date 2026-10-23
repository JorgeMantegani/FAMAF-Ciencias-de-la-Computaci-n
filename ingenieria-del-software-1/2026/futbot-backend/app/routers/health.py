import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthRead

"""Router del chequeo de salud de la API."""

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthRead)
def health(db: Session = Depends(get_db)) -> HealthRead:
    """Verifica que la API responde y que la base de datos contesta.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        # El detalle del error va al log y no a la respuesta
        logger.exception("Fallo el chequeo de conexion a la base de datos")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La base de datos no responde",
        ) from error

    return HealthRead(status="ok", database_connected=True)