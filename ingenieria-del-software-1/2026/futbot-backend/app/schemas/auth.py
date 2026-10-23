from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, SecretStr

""" Esquemas de autenticación y registro de usuarios."""

# Como recibe los datos
class UserRegister(BaseModel):
    # Datos de user
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=20)
    # Datos club
    club_name: str = Field(
        min_length=3, 
        max_length=50,
        alias="clubName",
    )
    avatar_url: str | None = Field( # Puede venir vacío
        default=None,
        alias="avatar",
    )

# Como guarda los datos
class ClubRead(BaseModel):
    name: str
    avatar_url: str | None = None

    model_config = {"from_attributes": True}

class UserRead(BaseModel):
    id: str
    username: str
    email: EmailStr
    club: ClubRead

    model_config = {"from_attributes": True}

"""Entrada y salida del inicio de sesion segun el contrato."""

class LoginRequest(BaseModel):
    email: str
    password: SecretStr


class LoginResponse(BaseModel):
    expires_at: int
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    club_id: UUID


class CurrentUserResponse(BaseModel):
    user_id: UUID
    club_id: UUID


class RefreshRequest(BaseModel):
    refresh_token: SecretStr
