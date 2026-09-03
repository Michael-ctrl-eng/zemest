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


class ProfileUpdateRequest(BaseModel):
    """Optional profile info for analytics/admin views (encrypted at rest).

    ``date_of_birth`` is an ISO date string (YYYY-MM-DD); the model rejects
    malformed dates, future dates and implausible ages (under 13 / over
    120). Identity fields (email/name) are NOT editable here — identity
    flows from the authenticated session only.
    """

    date_of_birth: str | None = None

    model_config = {
        "json_schema_extra": {"examples": [{"date_of_birth": "1996-04-17"}]}
    }

    @field_validator("date_of_birth")
    @classmethod
    def dob_valid(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        from datetime import date as _date

        try:
            parsed = _date.fromisoformat(v)
        except ValueError:
            raise ValueError("date_of_birth must be an ISO date (YYYY-MM-DD)")
        today = _date.today()
        age = today.year - parsed.year - (
            (today.month, today.day) < (parsed.month, parsed.day)
        )
        if parsed > today:
            raise ValueError("date_of_birth cannot be in the future")
        if age < 13:
            raise ValueError("users must be at least 13 years old")
        if age > 120:
            raise ValueError("date_of_birth looks implausible")
        return v


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
    plan: str = "free"
    trial: dict = {}  # {active, ends_at, days_left} — plan_service.trial_state

    model_config = {"from_attributes": True}
