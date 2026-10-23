from time import time
from app.core.security import decode_access_token
from app.models.auth_session import AuthSession
from app.services.auth import start_session


def test_fixed_session_expires_without_refresh(client, db, club, monkeypatch, fixed_session_settings):
    started = int(time())
    tokens = start_session(db, club.user)
    claims = decode_access_token(tokens.access_token)
    row = db.get(AuthSession, claims['sid'])
    assert started + 300 <= tokens.expires_at <= int(time()) + 300
    assert row.expires_at == tokens.expires_at == claims['exp']
    headers = {'Authorization': f'Bearer {tokens.access_token}'}
    assert client.get('/api/auth/me', headers=headers).status_code == 200
    assert client.post('/api/auth/refresh', json={'refresh_token': tokens.refresh_token}).status_code == 401
    monkeypatch.setattr('app.core.dependencies.time', lambda: tokens.expires_at)
    assert client.get('/api/auth/me', headers=headers).status_code == 401
    db.refresh(row)
    assert row.expires_at == tokens.expires_at
