"""Dependencias de autenticacion para endpoints privados."""
from time import time
from app.models.auth_session import AuthSession

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.club import Club
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def get_user_from_token(db: Session, token: str | None) -> User | None:
    """Devuelve el usuario dueño de un access token vigente, o None si no es válido."""
    if not isinstance(token, str) or not token:
        return None
    try:
        claims = decode_access_token(token)
        session = db.get(AuthSession, claims["sid"])
        user_id = claims["sub"]
    except (JWTError, ValueError, TypeError, KeyError):
        return None
    if (session is None or session.revoked or session.expires_at <= time()
            or session.user_id != user_id):
        return None
    return db.get(User, user_id)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o vencida",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user = get_user_from_token(db, credentials.credentials)
    if user is None:
        raise unauthorized
    return user


def get_current_club(user: User = Depends(get_current_user)) -> Club:
    if user.club is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o vencida",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user.club
