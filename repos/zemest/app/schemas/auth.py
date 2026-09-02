from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "Rahim", "email": "rahim@example.com", "password": "secret123"}]
        }
    }

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str) -> str:
        """Minimum viable policy: length 8+.

        Length dominates password strength; composition rules push users to
        predictable patterns (NIST SP 800-63B explicitly advises against them).
        bcrypt truncates at 72 bytes — the policy keeps input well inside that.
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return v

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name must not be blank")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FacebookLoginRequest(BaseModel):
    fb_access_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"


class RegisterAckResponse(BaseModel):
    """Anti-enumeration register response: identical for success AND duplicate.

    No tokens, no account-existence signal — the client logs in afterwards.
    """

    status: str = "accepted"
    message: str = "If the address is valid, your account has been created. Please log in."


class UserResponse(BaseModel):
    id: str
    name: str
    email: str | None
    fb_user_id: str | None
    is_superadmin: bool = False

    model_config = {"from_attributes": True}
