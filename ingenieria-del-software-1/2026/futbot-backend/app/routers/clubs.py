from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club
from app.db.session import get_db
from app.models.club import Club
from app.schemas.club_ranking import ClubRankingResponse
from app.services.club_ranking import get_club_ranking

router = APIRouter(prefix="/api/clubs", tags=["Clubs"])


@router.get("/ranking", response_model=ClubRankingResponse)
def club_ranking(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1),
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> ClubRankingResponse:
    """Ranking global ordenado por puntos descendentes y nombre ascendente.

    Requiere un JWT vigente. Las posiciones son globales, comenzando en 1;
    userClubRanking incluye al solicitante aunque no aparezca en la página.
    Una página fuera de rango devuelve 200 con items vacío y conserva los totales.
    """
    return get_club_ranking(db, club.id, page, size)
