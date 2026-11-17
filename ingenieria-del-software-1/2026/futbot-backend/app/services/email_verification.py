import logging
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from time import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.email_verification import EmailVerificationToken, VerificationRateLimit
from app.models.user import User
from app.services.email_sender import EmailSender, log_email_error

logger = logging.getLogger(__name__)
GENERIC_RESPONSE = {"detail": "Si corresponde, recibirás un correo de verificación."}


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def lock_user(db: Session, user_id: str) -> None:
    # También serializa operaciones en SQLite, donde FOR UPDATE no tiene efecto.
    db.execute(
        update(User).where(User.id == user_id).values(email_verified_at=User.email_verified_at)
    )


def issue_verification(db: Session, user: User, sender: EmailSender) -> None:
    lock_user(db, user.id)
    db.refresh(user)
    if user.email_verified_at is not None:
        db.commit()
        return
    now = datetime.now(timezone.utc)
    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
            EmailVerificationToken.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )
    token = token_urlsafe(48)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=now + timedelta(hours=get_settings().email_verification_expire_hours),
        )
    )
    email = user.email
    db.commit()
    parts = urlsplit(get_settings().email_verification_url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "token"]
    url = urlunsplit(parts._replace(query=urlencode(query + [("token", token)])))
    try:
        sender.send_verification(email, url)
    except Exception as error:
        log_email_error(logger, "verificación", error)


def verify_email(db: Session, token: str) -> dict[str, str]:
    digest = token_hash(token)
    user_id = db.scalar(
        select(EmailVerificationToken.user_id).where(EmailVerificationToken.token_hash == digest)
    )
    if user_id is None:
        verification_error("INVALID")
    lock_user(db, user_id)
    record = db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == digest)
        .execution_options(populate_existing=True)
    )
    if record is None or record.invalidated_at is not None:
        db.rollback()
        verification_error("INVALID")
    if record.consumed_at is not None:
        db.commit()
        return {"detail": "Correo verificado."}
    now = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:  # SQLite devuelve datetimes sin zona horaria.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        db.rollback()
        verification_error("EXPIRED")
    db.execute(
        update(User)
        .where(User.id == user_id, User.email_verified_at.is_(None))
        .values(email_verified_at=now)
    )
    record.consumed_at = now
    db.commit()
    return {"detail": "Correo verificado."}


def verification_error(reason: str) -> None:
    raise HTTPException(
        400,
        detail={
            "detail": "El enlace es inválido o venció.",
            "error_code": f"EMAIL_VERIFICATION_TOKEN_{reason}",
        },
    )


def allow_request(db: Session, scope: str, value: str, interval: int, limit: int) -> bool:
    key = scope + ":" + token_hash(value)
    now = int(time())
    try:
        with db.begin_nested():
            db.add(VerificationRateLimit(key=key, window_start=now, count=0))
            db.flush()
    except IntegrityError:
        pass
    db.execute(
        update(VerificationRateLimit)
        .where(
            VerificationRateLimit.key == key,
            VerificationRateLimit.window_start <= now - interval,
        )
        .values(window_start=now, count=0)
    )
    result = db.execute(
        update(VerificationRateLimit)
        .where(
            VerificationRateLimit.key == key,
            VerificationRateLimit.count < limit,
        )
        .values(count=VerificationRateLimit.count + 1)
    )
    allowed = result.rowcount == 1
    db.commit()
    return allowed


def resend_verification(db: Session, email: str, ip: str, sender: EmailSender) -> dict[str, str]:
    settings = get_settings()
    if not allow_request(
        db, "ip", ip, settings.email_resend_ip_window_seconds, settings.email_resend_ip_limit
    ):
        return GENERIC_RESPONSE
    if not allow_request(db, "email", email.casefold(), settings.email_resend_interval_seconds, 1):
        return GENERIC_RESPONSE
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        issue_verification(db, user, sender)
    return GENERIC_RESPONSE
