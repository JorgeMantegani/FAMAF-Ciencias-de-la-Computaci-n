from time import time

import pytest
from jose import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.models.auth_session import AuthSession
from app.services.auth import start_session


pytestmark = pytest.mark.usefixtures("enable_optional_refresh")


def bearer(tokens):
    return {'Authorization': f'Bearer {tokens.access_token}'}


def test_rotation_and_logout(client, db, club):
    original = start_session(db, club.user)
    other = start_session(db, club.user)
    row = db.scalar(select(AuthSession).where(AuthSession.id == decode_access_token(original.access_token)['sid']))
    assert row.refresh_hash != original.refresh_token
    response = client.post('/api/auth/refresh', json={'refresh_token': original.refresh_token})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    renewed = response.json()
    assert renewed['refresh_token'] != original.refresh_token
    assert client.post('/api/auth/refresh', json={'refresh_token': original.refresh_token}).status_code == 401
    headers = {'Authorization': f'Bearer {renewed["access_token"]}'}
    assert client.get('/api/auth/me', headers=headers).status_code == 200
    assert client.post('/api/auth/logout', headers=headers).status_code == 204
    db.expire_all()
    assert client.get('/api/auth/me', headers=headers).status_code == 401
    assert client.get('/api/auth/me', headers=bearer(original)).status_code == 401
    assert client.post('/api/auth/refresh', json={'refresh_token': renewed['refresh_token']}).status_code == 401
    assert client.post('/api/auth/logout', headers=headers).status_code == 204
    assert client.get('/api/auth/me', headers=bearer(other)).status_code == 200


def test_expired_access_can_refresh_and_logout(client, db, club):
    tokens = start_session(db, club.user)
    settings = get_settings()
    claims = decode_access_token(tokens.access_token)
    claims['exp'] = 1
    expired = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    headers = {'Authorization': f'Bearer {expired}'}
    assert client.get('/api/auth/me', headers=headers).status_code == 401
    refreshed = client.post('/api/auth/refresh', json={'refresh_token': tokens.refresh_token})
    assert refreshed.status_code == 200
    assert client.post('/api/auth/logout', headers=headers).status_code == 204
    assert client.post('/api/auth/refresh', json={'refresh_token': refreshed.json()['refresh_token']}).status_code == 401


@pytest.mark.parametrize('case', ['expired', 'deleted-user', 'unknown', 'access-token'])
def test_invalid_refresh(client, db, club, case):
    tokens = start_session(db, club.user)
    token = tokens.refresh_token
    if case == 'expired':
        row = db.get(AuthSession, decode_access_token(tokens.access_token)['sid'])
        row.expires_at = int(time()) - 1
        db.commit()
        assert client.get('/api/auth/me', headers=bearer(tokens)).status_code == 401
    elif case == 'deleted-user':
        db.delete(club.user)
        db.commit()
    elif case == 'unknown':
        token = 'unknown-refresh'
    else:
        token = tokens.access_token
    response = client.post('/api/auth/refresh', json={'refresh_token': token})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'


def test_logout_rejects_forgery(client, db, club):
    tokens = start_session(db, club.user)
    claims = decode_access_token(tokens.access_token)
    forged = jwt.encode(claims, 'wrong-key', algorithm=get_settings().jwt_algorithm)
    assert client.post('/api/auth/logout', headers={'Authorization': f'Bearer {forged}'}).status_code == 401
    assert client.get('/api/auth/me', headers=bearer(tokens)).status_code == 200
    assert client.post('/api/auth/logout').status_code == 401


def test_refresh_cannot_be_used_as_access(client, db, club):
    tokens = start_session(db, club.user)
    assert client.get('/api/auth/me', headers={'Authorization': f'Bearer {tokens.refresh_token}'}).status_code == 401


def test_concurrent_refresh_only_one_wins(db, club, engine, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import Session
    from app.services.auth import InvalidCredentialsError, refresh_session

    tokens = start_session(db, club.user)
    barrier = Barrier(2)
    original_scalar = Session.scalar

    def synchronized_read(self, statement, *args, **kwargs):
        result = original_scalar(self, statement, *args, **kwargs)
        if statement.column_descriptions[0].get('entity') is AuthSession:
            barrier.wait(timeout=30)
        return result

    monkeypatch.setattr(Session, 'scalar', synchronized_read)

    def renew():
        with Session(engine) as isolated:
            try:
                return refresh_session(isolated, tokens.refresh_token)
            except InvalidCredentialsError:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: renew(), range(2)))
    assert sum(result is not None for result in results) == 1
