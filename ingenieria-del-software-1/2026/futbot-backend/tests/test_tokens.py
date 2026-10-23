"""Verificacion de tokens en una ruta realmente protegida."""
import pytest
from jose import jwt

from app.core.config import get_settings
from app.services.auth import start_session
from app.core.security import decode_access_token


def assert_unauthorized(response):
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'


def test_me_uses_token_identity(client, db, club):
    response = client.get('/api/auth/me', headers={
        'Authorization': f'Bearer {start_session(db, club.user).access_token}',
    })
    assert response.status_code == 200
    assert response.json() == {'user_id': club.user_id, 'club_id': club.id}


@pytest.mark.parametrize('authorization', [None, 'Basic abc', 'Bearer', 'Bearer basura'])
def test_me_requires_bearer(client, authorization):
    headers = {} if authorization is None else {'Authorization': authorization}
    assert_unauthorized(client.get('/api/auth/me', headers=headers))


@pytest.mark.parametrize('case', [
    'expired', 'wrong-signature', 'wrong-algorithm', 'missing-exp',
    'missing-sub', 'empty-sub', 'numeric-sub', 'invalid-exp', 'unknown-user', 'missing-sid', 'wrong-sid',
])
def test_me_rejects_invalid_tokens(client, db, club, case):
    settings = get_settings()
    claims = decode_access_token(start_session(db, club.user).access_token)
    key = settings.jwt_secret_key
    algorithm = settings.jwt_algorithm
    if case == 'missing-sid':
        del claims['sid']
    elif case == 'wrong-sid':
        claims['sid'] = 'not-a-session'
    elif case == 'expired':
        claims['exp'] = 1
    elif case == 'wrong-signature':
        key = 'different-test-key'
    elif case == 'wrong-algorithm':
        algorithm = 'HS512' if algorithm != 'HS512' else 'HS256'
    elif case == 'missing-exp':
        del claims['exp']
    elif case == 'missing-sub':
        del claims['sub']
    elif case == 'empty-sub':
        claims['sub'] = ''
    elif case == 'numeric-sub':
        claims['sub'] = 42
    elif case == 'invalid-exp':
        claims['exp'] = None
    elif case == 'unknown-user':
        claims['sub'] = 'deleted-user'
    token = jwt.encode(claims, key, algorithm=algorithm)
    assert_unauthorized(client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}))


def test_me_rejects_deleted_user(client, db, club):
    token = start_session(db, club.user).access_token
    db.delete(club.user)
    db.commit()
    assert_unauthorized(client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}))


def test_me_without_club(client, db, club):
    token = start_session(db, club.user).access_token
    db.delete(club)
    db.commit()
    db.expire_all()
    response = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 409
