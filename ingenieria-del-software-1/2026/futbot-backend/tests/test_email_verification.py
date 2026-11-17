from concurrent.futures import ThreadPoolExecutor
import smtplib
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.init_db import crear_tablas
from app.models.auth_session import AuthSession
from app.models.email_verification import EmailVerificationToken, VerificationRateLimit
from app.models.user import User
from app.services.email_verification import allow_request, token_hash, verify_email

PAYLOAD = {
    "username": "new-player",
    "email": "new@example.com",
    "password": "password123",
    "clubName": "New Club",
}


def register(client):
    response = client.post("/api/auth/register", json=PAYLOAD)
    assert response.status_code == 201
    return response


def sent_token(sender, index=-1):
    return parse_qs(urlsplit(sender.messages[index][1]).query)["token"][0]


def verify(client, token):
    return client.post("/api/auth/verify-email", json={"token": token})


def resend(client, email=PAYLOAD["email"]):
    return client.post("/api/auth/resend-verification", json={"email": email})


def test_registration_and_verification(client, db, email_sender):
    response = register(client)
    token = sent_token(email_sender)
    user = db.get(User, response.json()["id"])
    assert user.email_verified_at is None
    record = db.scalar(select(EmailVerificationToken))
    assert record.token_hash == token_hash(token)
    assert token not in response.text
    assert len(email_sender.messages) == 1
    credentials = {"email": PAYLOAD["email"], "password": PAYLOAD["password"]}
    rejected = client.post("/api/auth/login", json=credentials)
    assert rejected.status_code == 403
    assert rejected.json()["error_code"] == "EMAIL_NOT_VERIFIED"
    assert db.scalar(select(AuthSession)) is None
    assert (
        client.post("/api/auth/login", json={**credentials, "password": "wrong"}).status_code == 401
    )
    assert verify(client, token).status_code == 200
    db.refresh(user)
    db.refresh(record)
    assert user.email_verified_at is not None
    assert record.consumed_at is not None
    verified_at = user.email_verified_at
    record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    assert verify(client, token).status_code == 200
    db.refresh(user)
    assert user.email_verified_at == verified_at
    assert client.post("/api/auth/login", json=credentials).status_code == 200


def test_expired_and_unknown_tokens(client, db, email_sender):
    register(client)
    record = db.scalar(select(EmailVerificationToken))
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    response = verify(client, sent_token(email_sender))
    assert response.status_code == 400
    assert response.json()["error_code"] == "EMAIL_VERIFICATION_TOKEN_EXPIRED"
    db.refresh(record)
    assert record.consumed_at is None
    assert db.get(User, record.user_id).email_verified_at is None
    assert verify(client, "unknown").json()["error_code"] == "EMAIL_VERIFICATION_TOKEN_INVALID"


def test_resend_replaces_token_and_hides_account_state(client, db, email_sender):
    register(client)
    old = sent_token(email_sender)
    response = resend(client)
    new = sent_token(email_sender)
    assert old != new
    assert verify(client, old).json()["error_code"] == "EMAIL_VERIFICATION_TOKEN_INVALID"
    assert resend(client).json() == response.json()
    assert len(email_sender.messages) == 2
    assert resend(client, "missing@example.com").json() == response.json()
    assert verify(client, new).status_code == 200
    db.query(VerificationRateLimit).delete()
    db.commit()
    assert resend(client).json() == response.json()
    assert len(email_sender.messages) == 2


def test_ip_limit_and_window_reset(client, db, email_sender, monkeypatch):
    monkeypatch.setattr(get_settings(), "email_resend_ip_limit", 1)
    register(client)
    expected = resend(client, "missing@example.com").json()
    assert resend(client).json() == expected
    assert len(email_sender.messages) == 1
    for row in db.scalars(select(VerificationRateLimit)):
        row.window_start = 0
    db.commit()
    assert resend(client).json() == expected
    assert len(email_sender.messages) == 2


def test_failed_delivery_preserves_account_and_allows_resend(client, db, email_sender):
    email_sender.fail = True
    response = register(client)
    user = db.get(User, response.json()["id"])
    assert user.email_verified_at is None
    assert user.club is not None
    assert db.scalar(select(EmailVerificationToken)) is not None
    email_sender.fail = False
    assert resend(client).status_code == 200
    assert verify(client, sent_token(email_sender)).status_code == 200


def test_delivery_error_logs_code_without_secrets(client, email_sender, monkeypatch, caplog):
    def fail(email, url):
        raise smtplib.SMTPDataError(554, f"private-provider-message {email} {url}".encode())

    monkeypatch.setattr(email_sender, "send_verification", fail)
    register(client)
    assert "SMTPDataError" in caplog.text
    assert "554" in caplog.text
    assert "private-provider-message" not in caplog.text
    assert PAYLOAD["email"] not in caplog.text
    assert "token=" not in caplog.text


def test_email_sent_only_after_commit(client, engine, email_sender, monkeypatch):
    original_send = email_sender.send_verification

    def check_committed(email, url):
        with Session(engine) as isolated:
            user = isolated.scalar(select(User).where(User.email == email))
            assert user is not None
            assert (
                isolated.scalar(
                    select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
                )
                is not None
            )
        original_send(email, url)

    monkeypatch.setattr(email_sender, "send_verification", check_committed)
    register(client)
    assert len(email_sender.messages) == 1


def test_concurrent_verification_is_idempotent(client, engine, email_sender):
    register(client)
    token = sent_token(email_sender)

    def consume(_):
        with Session(engine) as isolated:
            return verify_email(isolated, token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, range(2)))
    assert results == [{"detail": "Correo verificado."}] * 2


def test_rate_limit_is_shared_between_sessions(engine):
    def request(_):
        with Session(engine) as isolated:
            return allow_request(isolated, "email", "same@example.com", 60, 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(request, range(2))) == 1


def test_refresh_rejects_unverified_account(client, db, login_user, enable_optional_refresh):
    response = client.post(
        "/api/auth/login", json={"email": login_user.email, "password": "correct-password"}
    )
    login_user.email_verified_at = None
    db.commit()
    response = client.post(
        "/api/auth/refresh", json={"refresh_token": response.json()["refresh_token"]}
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "EMAIL_NOT_VERIFIED"


def test_migration_preserves_existing_users(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, username VARCHAR(50), "
                "email VARCHAR(255), password_hash VARCHAR(255), created_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, username, email, password_hash) "
                "VALUES ('old', 'old-user', 'old@example.com', 'hash')"
            )
        )
    crear_tablas(engine)
    crear_tablas(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id, email_verified_at FROM users")).one() == (
            "old",
            None,
        )
    assert "email_verification_tokens" in inspect(engine).get_table_names()
    engine.dispose()
