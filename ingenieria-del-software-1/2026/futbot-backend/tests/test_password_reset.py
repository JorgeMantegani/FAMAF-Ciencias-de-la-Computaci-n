import smtplib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import verify_password
from app.models.auth_session import AuthSession
from app.models.email_verification import EmailVerificationToken, VerificationRateLimit
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.email_sender import SMTPEmailSender
from app.services.email_verification import token_hash
from app.services.password_reset import reset_password
from app.ws.manager import manager

NEW_PASSWORD = "new-password-123"


@pytest.fixture
def login_user(login_user, db):
    # EmailStr rechaza dominios reservados .test en los endpoints públicos.
    login_user.email = "reset-user@example.com"
    db.commit()
    return login_user


def forgot(client, email):
    return client.post("/api/auth/forgot-password", json={"email": email})


def sent_token(sender):
    return parse_qs(urlsplit(sender.password_reset_messages[-1][1]).query)["token"][0]


def reset(client, token, password=NEW_PASSWORD):
    return client.post("/api/auth/reset-password", json={"token": token, "newPassword": password})


def expire_limits(db):
    for limit in db.scalars(select(VerificationRateLimit)):
        limit.window_start = 0
    db.commit()


def test_forgot_is_generic_and_stores_only_hash(client, db, login_user, email_sender):
    known = forgot(client, login_user.email)
    unknown = forgot(client, "missing@example.com")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(email_sender.password_reset_messages) == 1
    token = sent_token(email_sender)
    record = db.scalar(select(PasswordResetToken))
    assert record.token_hash == token_hash(token)
    assert token not in known.text and login_user.email not in known.text
    assert record.user_id == login_user.id
    assert record.consumed_at is None
    assert record.invalidated_at is None
    assert 29 * 60 < (record.expires_at - record.created_at).total_seconds() <= 30 * 60
    assert email_sender.messages == []
    db.refresh(login_user)
    assert verify_password("correct-password", login_user.password_hash)


def test_reset_changes_password_once_and_revokes_sessions(
    client,
    db,
    login_user,
    email_sender,
    enable_optional_refresh,
    monkeypatch,
):
    credentials = {"email": login_user.email, "password": "correct-password"}
    sessions = [client.post("/api/auth/login", json=credentials).json() for _ in range(2)]
    active_ids = set(db.scalars(select(AuthSession.id)))
    notifications = []
    monkeypatch.setattr(manager, "revoke_session", notifications.append)
    forgot(client, login_user.email)
    token = sent_token(email_sender)
    assert reset(client, token).status_code == 200
    db.refresh(login_user)
    record = db.scalar(select(PasswordResetToken))
    assert record.consumed_at is not None
    assert login_user.password_hash != NEW_PASSWORD
    assert login_user.password_hash.startswith("$2")
    assert verify_password(NEW_PASSWORD, login_user.password_hash)
    assert all(s.revoked for s in db.scalars(select(AuthSession)))
    assert set(notifications) == active_ids
    for session in sessions:
        assert (
            client.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {session['access_token']}"}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/auth/refresh", json={"refresh_token": session["refresh_token"]}
            ).status_code
            == 401
        )
    assert client.post("/api/auth/login", json=credentials).status_code == 401
    assert (
        client.post("/api/auth/login", json={**credentials, "password": NEW_PASSWORD}).status_code
        == 200
    )
    assert reset(client, token, "another-password").status_code == 400
    db.refresh(login_user)
    assert verify_password(NEW_PASSWORD, login_user.password_hash)


def test_tampered_and_unknown_tokens_do_not_consume_valid_token(
    client, db, login_user, email_sender
):
    forgot(client, login_user.email)
    token = sent_token(email_sender)
    for invalid in ("unknown", token + "x"):
        response = reset(client, invalid)
        assert response.status_code == 400
        assert response.json()["error_code"] == "PASSWORD_RESET_TOKEN_INVALID"
    assert db.scalar(select(PasswordResetToken)).consumed_at is None
    db.refresh(login_user)
    assert verify_password("correct-password", login_user.password_hash)
    assert reset(client, token).status_code == 200


def test_expired_token_is_consumed_without_changing_password(client, db, login_user, email_sender):
    forgot(client, login_user.email)
    token = sent_token(email_sender)
    record = db.scalar(select(PasswordResetToken))
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    response = reset(client, token)
    assert response.status_code == 400
    assert response.json()["error_code"] == "PASSWORD_RESET_TOKEN_EXPIRED"
    db.refresh(record)
    db.refresh(login_user)
    assert record.consumed_at is not None
    assert verify_password("correct-password", login_user.password_hash)
    assert reset(client, token).json()["error_code"] == "PASSWORD_RESET_TOKEN_INVALID"


def test_new_request_invalidates_old_token_and_email_rate_limit(
    client, db, login_user, email_sender
):
    first = forgot(client, login_user.email)
    old = sent_token(email_sender)
    assert forgot(client, login_user.email).json() == first.json()
    assert len(email_sender.password_reset_messages) == 1
    expire_limits(db)
    forgot(client, login_user.email)
    new = sent_token(email_sender)
    assert old != new
    assert reset(client, old).json()["error_code"] == "PASSWORD_RESET_TOKEN_INVALID"
    record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash(old))
    )
    assert record.invalidated_at is not None and record.consumed_at is not None
    assert reset(client, new).status_code == 200


def test_ip_limit_counts_unknown_accounts_and_resets(
    client, db, login_user, email_sender, monkeypatch
):
    monkeypatch.setattr(get_settings(), "password_reset_ip_limit", 1)
    expected = forgot(client, "missing@example.com")
    blocked = forgot(client, login_user.email)
    assert expected.status_code == blocked.status_code == 200
    assert expected.json() == blocked.json()
    assert email_sender.password_reset_messages == []
    expire_limits(db)
    assert forgot(client, login_user.email).status_code == 200
    assert len(email_sender.password_reset_messages) == 1


def test_smtp_failure_is_generic_and_does_not_expose_secrets(
    client, db, login_user, email_sender, monkeypatch, caplog
):
    def fail(email, url):
        raise smtplib.SMTPDataError(554, f"provider-secret {email} {url}".encode())

    monkeypatch.setattr(email_sender, "send_password_reset", fail)
    known = forgot(client, login_user.email)
    unknown = forgot(client, "missing@example.com")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert db.scalar(select(PasswordResetToken)) is not None
    assert "SMTPDataError" in caplog.text and "554" in caplog.text
    assert "provider-secret" not in caplog.text
    assert login_user.email not in caplog.text and "token=" not in caplog.text
    db.refresh(login_user)
    assert verify_password("correct-password", login_user.password_hash)


def test_token_committed_before_email_and_url_configurable(
    client, engine, login_user, email_sender, monkeypatch
):
    monkeypatch.setattr(
        get_settings(),
        "password_reset_url",
        "https://futbot.example/reset-password?lang=es&token=old",
    )
    monkeypatch.setattr(get_settings(), "password_reset_expire_minutes", 15)
    original = email_sender.send_password_reset

    def check(email, url):
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        assert parts.scheme == "https" and query["lang"] == ["es"]
        assert len(query["token"]) == 1 and query["token"] != ["old"]
        with Session(engine) as db:
            record = db.scalar(select(PasswordResetToken))
            assert record.token_hash == token_hash(query["token"][0])
            assert 14 * 60 < (record.expires_at - record.created_at).total_seconds() <= 15 * 60
        original(email, url)

    monkeypatch.setattr(email_sender, "send_password_reset", check)
    forgot(client, login_user.email)
    assert len(email_sender.password_reset_messages) == 1


def test_concurrent_reset_only_changes_password_once(client, engine, login_user, email_sender):
    forgot(client, login_user.email)
    token = sent_token(email_sender)

    def consume(password):
        with Session(engine) as db:
            try:
                reset_password(db, token, password)
                return password
            except HTTPException as error:
                assert error.status_code == 400
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, ["first-password", "second-password"]))
    winners = [value for value in results if value is not None]
    assert len(winners) == 1
    with Session(engine) as db:
        assert verify_password(winners[0], db.get(User, login_user.id).password_hash)


def test_reset_does_not_verify_email(client, db, login_user, email_sender):
    login_user.email_verified_at = None
    db.commit()
    forgot(client, login_user.email)
    assert reset(client, sent_token(email_sender)).status_code == 200
    db.refresh(login_user)
    assert login_user.email_verified_at is None
    response = client.post(
        "/api/auth/login", json={"email": login_user.email, "password": NEW_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "EMAIL_NOT_VERIFIED"


def test_reset_tokens_and_verification_tokens_are_not_interchangeable(
    client, db, login_user, email_sender
):
    verification_token = "verification-only"
    db.add(
        EmailVerificationToken(
            user_id=login_user.id,
            token_hash=token_hash(verification_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db.commit()
    assert reset(client, verification_token).status_code == 400
    forgot(client, login_user.email)
    assert (
        client.post("/api/auth/verify-email", json={"token": sent_token(email_sender)}).status_code
        == 400
    )
    assert reset(client, sent_token(email_sender)).status_code == 200


@pytest.mark.parametrize("password", ["short", "x" * 21])
def test_password_validation_does_not_consume_token(client, db, login_user, email_sender, password):
    forgot(client, login_user.email)
    token = sent_token(email_sender)
    assert reset(client, token, password).status_code == 422
    assert db.scalar(select(PasswordResetToken)).consumed_at is None
    assert reset(client, token).status_code == 200


def test_smtp_sender_sends_recovery_message(monkeypatch):
    calls = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, **kwargs):
            calls.append("tls")

        def login(self, username, password):
            calls.append("login")

        def send_message(self, message):
            calls.append(message)

    monkeypatch.setattr("app.services.email_sender.smtplib.SMTP", SMTP)
    monkeypatch.setattr(get_settings(), "smtp_username", "sender@example.com")
    monkeypatch.setattr(get_settings(), "smtp_starttls", True)
    SMTPEmailSender().send_password_reset(
        "recipient@example.com", "https://futbot.example/reset-password?token=test"
    )
    assert calls[:2] == ["tls", "login"]
    message = calls[2]
    assert message["To"] == "recipient@example.com"
    assert message["Subject"] == "Recuperá tu contraseña de FutBot"
    assert "?token=test" in message.get_content()


def test_reset_preserves_other_users_sessions(client, db, login_user, other_club, email_sender):
    other_session = AuthSession(
        user_id=other_club.user_id,
        refresh_hash="other-session-hash",
        expires_at=int(datetime.now(timezone.utc).timestamp()) + 3600,
    )
    db.add(other_session)
    db.commit()
    forgot(client, login_user.email)
    assert reset(client, sent_token(email_sender)).status_code == 200
    db.refresh(other_session)
    assert not other_session.revoked


def test_reset_rolls_back_password_and_token_if_commit_fails(
    client,
    engine,
    db,
    login_user,
    email_sender,
    monkeypatch,
):
    forgot(client, login_user.email)
    token = sent_token(email_sender)
    original_hash = login_user.password_hash
    with Session(engine) as isolated:

        def fail_commit():
            raise RuntimeError("simulated commit failure")

        monkeypatch.setattr(isolated, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated commit failure"):
            reset_password(isolated, token, NEW_PASSWORD)
    db.refresh(login_user)
    assert login_user.password_hash == original_hash
    assert db.scalar(select(PasswordResetToken)).consumed_at is None
    assert reset(client, token).status_code == 200
