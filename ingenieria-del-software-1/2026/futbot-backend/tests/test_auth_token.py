from time import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError

from app.core import dependencies
from app.core.dependencies import get_current_user, get_user_from_token
from app.models.auth_session import AuthSession
from app.models.user import User

"""Tests de la verificación de tokens compartida por HTTP y WebSocket."""


class FakeDb:
    """Base falsa: devuelve la sesión y el usuario que se le indiquen."""

    def __init__(self, session=None, user=None):
        self.session = session
        self.user = user

    def get(self, model, key):
        name = getattr(model, "__name__", "")
        if name == "AuthSession":
            return self.session
        if name == "User":
            return self.user
        return None


def valid_session(**overrides):
    data = {"user_id": "u1", "revoked": False, "expires_at": time() + 300}
    data.update(overrides)
    return SimpleNamespace(**data)


USER = SimpleNamespace(id="u1")


@pytest.fixture(autouse=True)
def token_decodes(monkeypatch):
    """Por defecto, cualquier token se decodifica a la sesión s1 del usuario u1."""
    monkeypatch.setattr(dependencies, "decode_access_token", lambda token: {"sid": "s1", "sub": "u1"})


# --- get_user_from_token ---


def test_token_vigente_devuelve_el_usuario() -> None:
    assert get_user_from_token(FakeDb(valid_session(), USER), "token") is USER


@pytest.mark.parametrize("token", [None, "", 123, 1.5, True, ["token"], {"token": "x"}])
def test_un_token_que_no_es_texto_o_esta_vacio_devuelve_none(token) -> None:
    assert get_user_from_token(FakeDb(valid_session(), USER), token) is None

def test_un_token_que_no_es_texto_no_llega_a_decodificarse(monkeypatch) -> None:
    llamadas = []
    monkeypatch.setattr(dependencies, "decode_access_token", lambda token: llamadas.append(token))

    assert get_user_from_token(FakeDb(valid_session(), USER), 123) is None
    assert llamadas == []

def test_token_que_no_se_puede_decodificar_devuelve_none(monkeypatch) -> None:
    def broken(token):
        raise JWTError("firma inválida")

    monkeypatch.setattr(dependencies, "decode_access_token", broken)

    assert get_user_from_token(FakeDb(valid_session(), USER), "token") is None


def test_token_sin_los_datos_esperados_devuelve_none(monkeypatch) -> None:
    monkeypatch.setattr(dependencies, "decode_access_token", lambda token: {"sub": "u1"})   # falta "sid"

    assert get_user_from_token(FakeDb(valid_session(), USER), "token") is None


def test_sesion_revocada_devuelve_none() -> None:
    assert get_user_from_token(FakeDb(valid_session(revoked=True), USER), "token") is None


def test_sesion_vencida_devuelve_none() -> None:
    assert get_user_from_token(FakeDb(valid_session(expires_at=time() - 1), USER), "token") is None


def test_sesion_de_otro_usuario_devuelve_none() -> None:
    assert get_user_from_token(FakeDb(valid_session(user_id="otro"), USER), "token") is None


def test_sesion_inexistente_devuelve_none() -> None:
    assert get_user_from_token(FakeDb(None, USER), "token") is None


def test_usuario_inexistente_devuelve_none() -> None:
    assert get_user_from_token(FakeDb(valid_session(), None), "token") is None


# --- get_current_user (el comportamiento HTTP no debe haber cambiado) ---


def test_get_current_user_con_token_vigente_devuelve_el_usuario() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    assert get_current_user(credentials, FakeDb(valid_session(), USER)) is USER


def test_get_current_user_sin_credenciales_responde_401() -> None:
    with pytest.raises(HTTPException) as error:
        get_current_user(None, FakeDb(valid_session(), USER))

    assert error.value.status_code == 401
    assert error.value.detail == "Sesión inválida o vencida"
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_get_current_user_con_sesion_revocada_responde_401() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    with pytest.raises(HTTPException) as error:
        get_current_user(credentials, FakeDb(valid_session(revoked=True), USER))

    assert error.value.status_code == 401


def test_la_misma_sesion_pasa_vigente_y_falla_vencida() -> None:
    assert get_user_from_token(FakeDb(valid_session(expires_at=time() + 300), USER), "token") is USER
    assert get_user_from_token(FakeDb(valid_session(expires_at=time() - 1), USER), "token") is None


def test_la_misma_sesion_pasa_activa_y_falla_revocada() -> None:
    assert get_user_from_token(FakeDb(valid_session(revoked=False), USER), "token") is USER
    assert get_user_from_token(FakeDb(valid_session(revoked=True), USER), "token") is None


def test_el_usuario_se_busca_con_el_sub_del_token() -> None:
    pedidos = []

    class Db(FakeDb):
        def get(self, model, key):
            pedidos.append((getattr(model, "__name__", ""), key))
            return super().get(model, key)

    assert get_user_from_token(Db(valid_session(), USER), "token") is USER
    assert pedidos == [("AuthSession", "s1"), ("User", "u1")]