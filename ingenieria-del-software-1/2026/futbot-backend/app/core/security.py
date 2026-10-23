"""Verificacion de contrasenas y emision de tokens de acceso."""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

""" hashing de contraseñas """
def hash_password(password: str) -> str:
    return password_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(user_id: str, session_id: str, *, expires_at: datetime | None = None) -> str:
    settings = get_settings()
    expires_at = expires_at or (datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes))
    return jwt.encode(
        {"sub": user_id, "sid": session_id, "exp": expires_at},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, *, verify_exp: bool = True) -> dict:
    """Verifica el JWT y devuelve sus claims; solo logout omite el vencimiento."""
    settings = get_settings()
    claims = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require_exp": verify_exp, "require_sub": True, "verify_exp": verify_exp},
    )
    if "exp" not in claims:
        raise JWTError("Missing expiration")
    subject = claims["sub"]
    if not isinstance(subject, str) or not subject.strip():
        raise JWTError("Invalid subject")
    if not isinstance(claims.get("sid"), str) or not claims["sid"].strip():
        raise JWTError("Missing session")
    return claims
