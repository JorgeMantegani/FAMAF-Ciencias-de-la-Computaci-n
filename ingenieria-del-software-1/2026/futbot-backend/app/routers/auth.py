
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
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
from app.schemas.auth import (
    VerifyEmailRequest, ResendVerificationRequest, ForgotPasswordRequest, ResetPasswordRequest,
)
from app.services.password_reset import (
    GENERIC_RESPONSE as PASSWORD_RESET_RESPONSE,
    process_password_reset,
    reset_password,
)
from app.services.auth import EmailNotVerifiedError
from app.services.email_sender import EmailSender, get_email_sender
from app.services.email_verification import issue_verification, verify_email, resend_verification

"""router = APIRouter(prefix="/api/auth", tags=["register"])"""
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    data: UserRegister,
    sender: EmailSender = Depends(get_email_sender),
    db: Session = Depends(get_db),
) -> UserRead:
    user = create_user_with_club(db, data)
    issue_verification(db, user, sender)
    return user

@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login_endpoint(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        response.headers["Cache-Control"] = "no-store"
        return login(db, payload.email, payload.password.get_secret_value())
    except EmailNotVerifiedError as error:
        raise HTTPException(403, detail={"detail": "Debés verificar tu correo.",
                            "error_code": "EMAIL_NOT_VERIFIED"}) from error
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
    except EmailNotVerifiedError as error:
        raise HTTPException(403, detail={"detail": "Debés verificar tu correo.",
                            "error_code": "EMAIL_NOT_VERIFIED"}) from error
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


@router.post("/verify-email")
def verify_email_endpoint(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    return verify_email(db, payload.token.get_secret_value())


@router.post("/resend-verification")
def resend_verification_endpoint(payload: ResendVerificationRequest, request: Request,
                                 db: Session = Depends(get_db),
                                 sender: EmailSender = Depends(get_email_sender)):
    ip = request.client.host if request.client else "unknown"
    return resend_verification(db, str(payload.email), ip, sender)


@router.post("/forgot-password")
def forgot_password_endpoint(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    ip = request.client.host if request.client else "unknown"
    background_tasks.add_task(process_password_reset, db.get_bind(), str(payload.email), ip, sender)
    return PASSWORD_RESET_RESPONSE


@router.post("/reset-password")
def reset_password_endpoint(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    return reset_password(
        db, payload.token.get_secret_value(), payload.new_password.get_secret_value(),
    )
