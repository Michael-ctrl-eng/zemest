from __future__ import annotations

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "Rahim", "email": "rahim@example.com", "password": "secret123"}]
        }
    }


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FacebookLoginRequest(BaseModel):
    fb_access_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str | None
    fb_user_id: str | None

    model_config = {"from_attributes": True}
