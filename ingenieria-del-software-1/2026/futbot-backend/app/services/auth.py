"""Autenticacion de cuentas existentes."""
from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_urlsafe
from time import time
from sqlalchemy import select, update
from app.core.config import get_settings
from app.models.auth_session import AuthSession
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginResponse


class InvalidCredentialsError(Exception):
    pass


class MissingClubError(Exception):
    pass


def login(db: Session, email: str, password: str) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    if user.club is None:
        raise MissingClubError
    return start_session(db, user)


def hash_refresh(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def session_response(user: User, session: AuthSession, refresh_token: str) -> LoginResponse:
    expires_at = min(session.expires_at, int(time()) + get_settings().jwt_expire_minutes * 60)
    return LoginResponse(
        expires_at=expires_at,
        access_token=create_access_token(user.id, session.id, expires_at=datetime.fromtimestamp(expires_at, timezone.utc)),
        refresh_token=refresh_token, club_id=user.club.id,
    )


def start_session(db: Session, user: User) -> LoginResponse:
    token = token_urlsafe(48)
    settings = get_settings()
    lifetime = settings.refresh_expire_days * 86400 if settings.refresh_enabled else settings.jwt_expire_minutes * 60
    session = AuthSession(user_id=user.id, refresh_hash=hash_refresh(token),
                          expires_at=int(time()) + lifetime)
    db.add(session)
    db.flush()
    response = session_response(user, session, token)
    db.commit()
    return response


def refresh_session(db: Session, token: str) -> LoginResponse:
    if not get_settings().refresh_enabled:
        raise InvalidCredentialsError
    old_hash = hash_refresh(token)
    session = db.scalar(select(AuthSession).where(
        AuthSession.refresh_hash == old_hash,
        AuthSession.revoked.is_(False), AuthSession.expires_at > time(),
    ))
    if session is None:
        raise InvalidCredentialsError
    user = db.get(User, session.user_id)
    if user is None:
        raise InvalidCredentialsError
    if user.club is None:
        raise MissingClubError
    new_token = token_urlsafe(48)
    # Comparar y actualizar en una operación: un refresh solo puede consumirse una vez.
    result = db.execute(update(AuthSession).where(
        AuthSession.id == session.id, AuthSession.refresh_hash == old_hash,
        AuthSession.revoked.is_(False), AuthSession.expires_at > time(),
    ).values(refresh_hash=hash_refresh(new_token)))
    if result.rowcount != 1:
        db.rollback()
        raise InvalidCredentialsError
    response = session_response(user, session, new_token)
    db.commit()
    return response
