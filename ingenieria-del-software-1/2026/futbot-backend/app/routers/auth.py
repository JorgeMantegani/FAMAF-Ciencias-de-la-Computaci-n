
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import update
from app.core.dependencies import bearer
from app.core.security import decode_access_token
from app.models.auth_session import AuthSession
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.user import User
from app.db.session import get_db
from app.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse, RefreshRequest
from app.services.auth import InvalidCredentialsError, MissingClubError, login, refresh_session
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.schemas.auth import UserRead, UserRegister
from app.services.auth_services import create_user_with_club
from app.ws.manager import manager

"""router = APIRouter(prefix="/api/auth", tags=["register"])"""
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    data: UserRegister,
    db: Session = Depends(get_db),
) -> UserRead:
    return create_user_with_club(db, data)

@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login_endpoint(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        response.headers["Cache-Control"] = "no-store"
        return login(db, payload.email, payload.password.get_secret_value())
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
        
        
    #posiblemente innecesario, ya que para registrarse el usuario esta obligado a crear un club para asociarse, pero queda por si se rompe algo
        
    except MissingClubError as error:                                               
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cuenta no tiene un club asociado",
        ) from error


@router.get("/me", response_model=CurrentUserResponse)
def current_user_endpoint(user: User = Depends(get_current_user)) -> CurrentUserResponse:
    if user.club is None:
        raise HTTPException(status_code=409, detail="La cuenta no tiene un club asociado")
    return CurrentUserResponse(user_id=user.id, club_id=user.club.id)


@router.post("/refresh", response_model=LoginResponse)
def refresh_endpoint(payload: RefreshRequest, response: Response,
                     db: Session = Depends(get_db)) -> LoginResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        return refresh_session(db, payload.refresh_token.get_secret_value())
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail="Sesión inválida o vencida",
                            headers={"WWW-Authenticate": "Bearer"}) from error
    except MissingClubError as error:
        raise HTTPException(status_code=409, detail="La cuenta no tiene un club asociado") from error


@router.post("/logout", status_code=204)
def logout_endpoint(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                    db: Session = Depends(get_db)) -> Response:
    try:
        if credentials is None:
            raise JWTError("Missing token")
        # Un access token vencido todavía permite revocar su propia sesión.
        claims = decode_access_token(credentials.credentials, verify_exp=False)
    except (JWTError, ValueError, TypeError) as error:
        raise HTTPException(status_code=401, detail="Sesión inválida",
                            headers={"WWW-Authenticate": "Bearer"}) from error
    db.execute(update(AuthSession).where(
        AuthSession.id == claims["sid"], AuthSession.user_id == claims["sub"],
    ).values(revoked=True))
    db.commit()
    manager.revoke_session(claims["sid"])
    return Response(status_code=204)
