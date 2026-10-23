from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User


def test_login_success(client: TestClient, login_user: User) -> None:
    settings = get_settings()
    started_at = int(datetime.now(timezone.utc).timestamp())
    response = client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": "correct-password"},
    )
    finished_at = int(datetime.now(timezone.utc).timestamp())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "refresh_token", "token_type", "club_id", "expires_at"}
    assert body["token_type"] == "bearer"
    assert response.headers["cache-control"] == "no-store"
    assert client.get('/api/auth/me', headers={'Authorization': f'Bearer {body["access_token"]}'}).status_code == 200
    assert client.post('/api/auth/refresh', json={'refresh_token': body['refresh_token']}).status_code == 401
    assert body["club_id"] == login_user.club.id  # assert body["club_id"] == str(login_user.club.id)
    claims = jwt.decode(
        body["access_token"], settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert claims["sub"] == login_user.id #str(login_user.id)
    assert body["expires_at"] == claims["exp"]
    lifetime = settings.jwt_expire_minutes * 60
    assert started_at + lifetime <= claims["exp"] <= finished_at + lifetime
    assert set(claims) == {"sub", "sid", "exp"}
    with pytest.raises(JWTError):
        jwt.decode(body["access_token"], "wrong-key", algorithms=[settings.jwt_algorithm])


@pytest.mark.parametrize("email,password", [
    ("missing@futbot.test", "correct-password"),
    ("login@futbot.test", "wrong-password"),
])
def test_login_invalid_credentials(
    client: TestClient, login_user: User, email: str, password: str
) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Credenciales inválidas", "error_code": "UNAUTHORIZED"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_without_club(client: TestClient, db: Session, login_user: User) -> None:
    db.delete(login_user.club)
    db.commit()
    db.expire_all()
    response = client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": "correct-password"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "La cuenta no tiene un club asociado", "error_code": "CONFLICT"}


@pytest.mark.parametrize("payload", [{}, {"email": "login@futbot.test"}])
def test_login_requires_credentials(client: TestClient, payload: dict) -> None:
    assert client.post("/api/auth/login", json=payload).status_code == 422
