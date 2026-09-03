from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

import asyncio

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import (
    FacebookLoginRequest,
    LoginRequest,
    LogoutRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterAckResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# Per-IP rate limiting (brute-force protection). Uses the same limiter
# singleton that main.py wires onto app.state (in-memory storage when
# Redis is not configured).
from app.middleware.rate_limit import get_limiter as _get_limiter

try:
    _limiter = _get_limiter()
except Exception:  # pragma: no cover — soft dependency
    _limiter = None


@router.post("/register", response_model=RegisterAckResponse, status_code=202)
@_limiter.limit("3/minute")
async def register(request: Request, req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new account.

    Anti-enumeration: returns the same 202 + body whether the account was
    created, the email is already taken, or policy refused the signup
    (disposable email / IP ceiling). Account existence must not be
    discoverable from status code, body, or response timing (the duplicate
    and refused paths burn an equal-cost bcrypt hash).

    New accounts get a 7-day trial unless their signup IP already consumed
    one (see auth_service.register_user).
    """
    # Client IP for trial-abuse prevention. request.client can be None under
    # some ASGI test transports — the service treats that as "no IP" (trial
    # still granted, IP rules inert).
    signup_ip = None
    if request.client and request.client.host:
        signup_ip = request.client.host
    try:
        await auth_service.register_user(db, req.name, req.email, req.password, signup_ip=signup_ip)
        await db.commit()
    except (auth_service.EmailAlreadyRegistered, auth_service.RegistrationRefused):
        # Burn the same bcrypt cost a genuine registration just paid so the
        # response timing does not leak which path executed.
        from app.utils.security import burn_password_timing

        await asyncio.to_thread(burn_password_timing, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegisterAckResponse()


@router.post("/login", response_model=TokenResponse)
@_limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        pair = await auth_service.login_user(db, req.email, req.password)
        await db.commit()
        return TokenResponse(**pair)
    except auth_service.AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


@router.post("/facebook", response_model=TokenResponse)
async def facebook_login(req: FacebookLoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        pair = await auth_service.login_with_facebook(db, req.fb_access_token)
        await db.commit()
        return TokenResponse(**pair)
    except auth_service.AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Rotate a refresh token.

    Single-use: each refresh token is exchanged exactly once. Presenting a
    token that was already consumed revokes every session for the account
    (reuse = theft signal per OAuth 2.0 Security BCP).
    """
    try:
        pair = await auth_service.rotate_refresh_token(db, req.refresh_token)
        await db.commit()
        return TokenResponse(**pair)
    except auth_service.AuthError as e:
        # Reuse detection stages revocations BEFORE raising — those writes
        # must SURVIVE the error path (rollback here would un-revoke the
        # stolen-token family, re-opening the replay window).
        try:
            await db.commit()
        except Exception:  # noqa: BLE001 — nothing staged on plain 401
            await db.rollback()
        raise HTTPException(status_code=e.status, detail=e.message)


@router.post("/logout", status_code=204)
async def logout(
    req: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Revoke one refresh token (idempotent, always 204)."""
    await auth_service.revoke_refresh_token(db, req.refresh_token)
    await db.commit()


@router.get("/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user)):
    from app.services.plan_service import effective_plan, trial_state

    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        fb_user_id=user.fb_user_id,
        is_superadmin=bool(user.is_superadmin),
        plan=effective_plan(user),
        trial=trial_state(user),
    )


@router.patch("/me/profile", response_model=UserResponse)
async def update_my_profile(
    req: ProfileUpdateRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set optional profile info (date of birth) — encrypted at rest.

    Feeds the analytics/admin views ("date of birth of the user" in the
    product requirements). Validation lives in the schema (ISO date,
    no future dates, 13–120 years).
    """
    from app.services.plan_service import effective_plan, trial_state

    if "date_of_birth" in req.model_fields_set:
        user.date_of_birth = req.date_of_birth or None
    await db.commit()
    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        fb_user_id=user.fb_user_id,
        is_superadmin=bool(user.is_superadmin),
        plan=effective_plan(user),
        trial=trial_state(user),
    )
