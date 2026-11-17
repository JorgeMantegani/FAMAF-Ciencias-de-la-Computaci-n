import asyncio

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club, get_current_user, get_user_from_token
from app.db.session import get_db
from app.models.club import Club
from app.models.user import User
from app.schemas.league import (
    CreateLeague,
    JoinLeagueRequest,
    JoinLeagueResponse,
    LeagueDetailRead,
    LeagueResponse,
    ListLeagueResponse,
    LeagueStanding,
)
from app.ws.leagues_hub import leagues_hub
from app.services.exceptions_league import LeagueNotFound
from app.models.club import Club
from app.services.exceptions_player import AppException
from app.services.league_service import (
    LeagueService,
    create_league,
    get_league,
    get_league_by_code,
    join_league,
    get_league_standings,
)

router = APIRouter(
    prefix="/api",
    tags=["Leagues"]
)

STANDINGS_AUTH_TIMEOUT_SECONDS = 5


@router.get(
    "/leagues",
    response_model=list[ListLeagueResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar ligas registradas"
)
def list_leagues(
    name: str | None = Query(default=None, max_length=80, description="Filtra por nombre (contiene)"),
    current_user: User = Depends(get_current_user),     # valida el token: sin él responde 401
    db: Session = Depends(get_db),
):
    return LeagueService(db).list_leagues(name=name)


@router.post("/leagues", status_code=201, response_model=LeagueResponse)
def crear_liga_endpoint(
    league_data: CreateLeague,
    db: Session = Depends(get_db),
    current_club: Club = Depends(get_current_club),
) -> LeagueResponse:
    try:
        league = create_league(db, league_data, current_club)
        return league
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
@router.post("/leagues/{league_id}/join", response_model=JoinLeagueResponse)
def join_league_endpoint(
    league_id: str,
    payload: JoinLeagueRequest,
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> JoinLeagueResponse:
    try:
        return join_league(db, league_id, club, payload)
    except AppException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"detail": e.message, "error_code": e.code},
        ) from e


@router.get("/leagues/by-code/{code}", response_model=LeagueDetailRead)
def read_league_by_code_endpoint(
    code: str,
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> LeagueDetailRead:
    try:
        return get_league_by_code(db, code, club)
    except AppException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"detail": e.message, "error_code": e.code},
        ) from e


@router.get("/leagues/{league_id}", response_model=LeagueDetailRead)
def read_league_endpoint(
    league_id: str,
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> LeagueDetailRead:
    try:
        return get_league(db, league_id, club)
    except AppException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"detail": e.message, "error_code": e.code},
        ) from e
        

@router.get(
    "/leagues/{league_id}/standings",
    response_model=list[LeagueStanding],
    status_code=status.HTTP_200_OK,
    summary="Consultar la tabla de posiciones de una liga",
)
def league_standings(
    league_id: str,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LeagueStanding]:
    try:
        return get_league_standings(db, league_id)
    except LeagueNotFound as error:
        raise HTTPException(status_code=404, detail=error.message) from error


@router.websocket("/leagues/{league_id}/standings/ws")
async def league_standings_ws(
    websocket: WebSocket,
    league_id: str,
    db: Session = Depends(get_db),
) -> None:
    await websocket.accept()
    try:
        first = await asyncio.wait_for(
            websocket.receive_json(), timeout=STANDINGS_AUTH_TIMEOUT_SECONDS
        )
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, ValueError):
        await websocket.close(code=4401)
        return

    user = None
    if isinstance(first, dict) and first.get("type") == "auth":
        user = get_user_from_token(db, first.get("token"))
    if user is None:
        await websocket.close(code=4401)
        return

    leagues_hub.add_standings_subscriber(websocket, league_id)
    try:
        try:
            standings = get_league_standings(db, league_id)
        except LeagueNotFound:
            await websocket.close(code=4404)
            return
        finally:
            db.close()
        await websocket.send_json({
            "type": "standings",
            "league_id": league_id,
            "standings": [row.model_dump(mode="json") for row in standings],
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        leagues_hub.remove(websocket)