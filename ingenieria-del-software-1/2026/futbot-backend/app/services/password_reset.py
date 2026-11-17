"""Recuperación de contraseña con tokens de un solo uso y sesiones revocables."""

import logging
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.auth_session import AuthSession
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.email_sender import EmailSender, log_email_error
from app.services.email_verification import allow_request, lock_user, token_hash
from app.ws.manager import manager

logger = logging.getLogger(__name__)
GENERIC_RESPONSE = {"detail": "Si corresponde, recibirás un correo para recuperar tu contraseña."}


def process_password_reset(engine: Engine, email: str, ip: str, sender: EmailSender) -> None:
    # Se ejecuta después de responder, para no revelar la existencia de la cuenta
    # mediante la demora del servidor SMTP. Usa su propia sesión de base de datos.
    try:
        with Session(engine) as db:
            forgot_password(db, email, ip, sender)
    except Exception as error:
        log_email_error(logger, "recuperación", error)


def forgot_password(db: Session, email: str, ip: str, sender: EmailSender) -> None:
    settings = get_settings()
    if not allow_request(
        db,
        "reset-ip",
        ip,
        settings.password_reset_ip_window_seconds,
        settings.password_reset_ip_limit,
    ):
        return
    if not allow_request(
        db, "reset-email", email.casefold(), settings.password_reset_interval_seconds, 1
    ):
        return
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        return
    lock_user(db, user.id)
    now = datetime.now(timezone.utc)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )
    token = token_urlsafe(48)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=now + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    # El token debe estar disponible para validarse antes de enviar su enlace.
    db.commit()
    parts = urlsplit(settings.password_reset_url)
    query = [(key, value) for key, value in parse_qsl(parts.query) if key != "token"]
    url = urlunsplit(parts._replace(query=urlencode(query + [("token", token)])))
    try:
        sender.send_password_reset(email, url)
    except Exception as error:
        log_email_error(logger, "recuperación", error)


def reset_error(reason: str) -> None:
    raise HTTPException(
        400,
        detail={
            "detail": "El enlace de recuperación es inválido o venció.",
            "error_code": f"PASSWORD_RESET_TOKEN_{reason}",
        },
    )


def reset_password(db: Session, token: str, new_password: str) -> dict[str, str]:
    digest = token_hash(token)
    user_id = db.scalar(
        select(PasswordResetToken.user_id).where(PasswordResetToken.token_hash == digest)
    )
    if user_id is None:
        reset_error("INVALID")
    lock_user(db, user_id)
    record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == digest)
        .execution_options(populate_existing=True)
    )
    if record is None or record.consumed_at is not None:
        db.rollback()
        reset_error("INVALID")
    now = datetime.now(timezone.utc)
    if record.invalidated_at is not None:
        record.consumed_at = now
        db.commit()
        reset_error("INVALID")
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        record.consumed_at = now
        db.commit()
        reset_error("EXPIRED")
    try:
        db.execute(
            update(User).where(User.id == user_id).values(password_hash=hash_password(new_password))
        )
        record.consumed_at = now
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.id != record.id,
                PasswordResetToken.consumed_at.is_(None),
                PasswordResetToken.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        session_ids = list(
            db.scalars(
                select(AuthSession.id).where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked.is_(False),
                )
            )
        )
        db.execute(update(AuthSession).where(AuthSession.user_id == user_id).values(revoked=True))
        db.commit()
    except Exception:
        db.rollback()
        raise
    for session_id in session_ids:
        manager.revoke_session(session_id)
    return {"detail": "Contraseña actualizada. Iniciá sesión con tu nueva contraseña."}
