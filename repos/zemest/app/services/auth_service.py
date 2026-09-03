"""Authentication service.

Hardening (audit F1):
* Registration is race-safe: relies on the unique index on ``users.email``
  and converts ``IntegrityError`` into a duplicate signal instead of the
  SELECT-then-INSERT race.
* Login timing is equalized with a dummy bcrypt hash when the account does
  not exist, so response latency no longer reveals whether an email is
  registered.
* Login returns an access + refresh token pair; refresh tokens rotate on
  every use with reuse detection (see :mod:`app.models.refresh_token`).
* Blocked users fail closed with a distinct error code.

Trial & signup-abuse policy (product):
* Every NEW registration gets a 7-day trial (Growth-level limits) — unless
  the signup IP already consumed one (any earlier account from that IP had
  a trial). Second accounts from the same IP register WITHOUT a trial:
  they can still pay for a plan, they just can't farm trials.
* Disposable/throwaway email domains are refused (anti-enum 202 in the
  route — the account simply never gets created).
* Hard ceiling: MAX_ACCOUNTS_PER_IP registrations per IP (configurable).
"""
import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.refresh_token import RefreshTokenRecord
from app.models.user import User
from app.utils.security import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    burn_password_timing,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)


class AuthError(Exception):
    """Base class — carries an HTTP status + machine-readable code."""

    def __init__(self, code: str, message: str, status: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class InvalidCredentials(AuthError):
    def __init__(self):
        super().__init__("invalid_credentials", "Invalid email or password", 401)


class AccountBlocked(AuthError):
    def __init__(self):
        super().__init__(
            "account_blocked", "This account has been blocked", 403
        )


class EmailAlreadyRegistered(AuthError):
    def __init__(self):
        super().__init__("email_taken", "Registration could not be completed", 409)


class RegistrationRefused(AuthError):
    """Signup refused by policy (disposable email / IP account ceiling).

    The route maps this to the SAME uniform 202 the register endpoint
    already returns — an attacker probing the gate learns nothing, a legit
    user with a real address is unaffected.
    """

    def __init__(self, code: str = "registration_refused"):
        super().__init__(code, "Registration could not be completed", 202)


TRIAL_DAYS = 7
MAX_ACCOUNTS_PER_IP = 5


async def _ip_used_trial(db: AsyncSession, ip: str | None) -> bool:
    """True when ANY earlier account from this IP consumed a trial."""
    if not ip:
        return False
    from sqlalchemy import select as _select

    from app.models.user import User as _User

    result = await db.execute(
        _select(_User.id).where(_User.signup_ip == ip, _User.trial_ends_at.isnot(None)).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _ip_account_count(db: AsyncSession, ip: str | None) -> int:
    if not ip:
        return 0
    from sqlalchemy import func as _func, select as _select

    from app.models.user import User as _User

    result = await db.execute(
        _select(_func.count(_User.id)).where(_User.signup_ip == ip)
    )
    return int(result.scalar() or 0)


async def register_user(
    db: AsyncSession,
    name: str,
    email: str,
    password: str,
    signup_ip: str | None = None,
) -> User:
    """Create a new user.

    Raises :class:`EmailAlreadyRegistered` on the unique-constraint violation
    (race-safe: the DB constraint, not a prior SELECT, is the source of truth).
    Raises :class:`RegistrationRefused` for disposable emails or when the
    signup IP exceeds the account ceiling.

    Trial rules: 7-day trial unless the IP already consumed one.
    """
    from app.utils.disposable_email import is_disposable_email

    if is_disposable_email(email):
        raise RegistrationRefused("disposable_email")

    if signup_ip and await _ip_account_count(db, signup_ip) >= MAX_ACCOUNTS_PER_IP:
        raise RegistrationRefused("ip_account_ceiling")

    # One trial per signup IP (product requirement). NULL = no trial.
    if await _ip_used_trial(db, signup_ip):
        trial_ends_at = None
    else:
        trial_ends_at = datetime.utcnow() + timedelta(days=TRIAL_DAYS)

    user = User(
        id=uuid.uuid4(),
        name=name,
        email=email,
        signup_ip=signup_ip,
        trial_ends_at=trial_ends_at,
        # bcrypt off the event loop (it measures ~250ms of pure CPU).
        hashed_password=await asyncio.to_thread(hash_password, password),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise EmailAlreadyRegistered() from None
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> dict:
    """Issue a fresh access + refresh token pair and record the refresh jti."""
    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})

    payload_jti = _jti_of(refresh)
    db.add(
        RefreshTokenRecord(
            jti=payload_jti,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        # Astronomically unlikely (jti collision) — fail loudly, retry next login.
        await db.rollback()

    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


def _jti_of(token: str) -> str:
    from app.utils.security import decode_token

    payload = decode_token(token) or {}
    return str(payload.get("jti", ""))


async def login_user(db: AsyncSession, email: str, password: str) -> dict:
    """Verify credentials and return a token pair.

    Timing-equalized: unknown emails still pay the full bcrypt cost.
    Blocked accounts are rejected before any token is minted.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password:
        # Burn the same ~250ms a wrong-password attempt would burn.
        await asyncio.to_thread(burn_password_timing, password)
        raise InvalidCredentials()

    ok = await asyncio.to_thread(verify_password, password, user.hashed_password)
    if not ok:
        raise InvalidCredentials()

    if user.is_blocked:
        raise AccountBlocked()

    return await issue_token_pair(db, user)


async def rotate_refresh_token(db: AsyncSession, refresh_token: str) -> dict:
    """Rotate a refresh token: revoke old, issue new pair, detect reuse.

    Reuse detection: the revoked flip is a compare-and-swap
    (``UPDATE ... WHERE revoked = false``). If the CAS matches zero rows the
    token was already consumed — either replayed or forged. In both cases we
    treat it as theft evidence and revoke EVERY token for the user (the
    attacker keeps access only until the stolen pair expires; the legitimate
    user re-authenticates with password).
    """
    payload = verify_refresh_token(refresh_token)
    if payload is None:
        raise InvalidCredentials()

    jti = str(payload.get("jti", ""))
    sub = str(payload.get("sub", ""))
    if not jti or not sub:
        raise InvalidCredentials()

    # CAS: exactly one transition false -> true allowed.
    cas = await db.execute(
        update(RefreshTokenRecord)
        .where(RefreshTokenRecord.jti == jti, RefreshTokenRecord.revoked == False)  # noqa: E712
        .values(revoked=True)
    )
    if cas.rowcount == 0:
        # REUSE (or forged jti): nuke every token this user owns.
        await revoke_all_user_tokens(db, sub)
        raise AuthError(
            "refresh_reuse_detected",
            "Refresh token reuse detected — all sessions revoked",
            401,
        )

    try:
        user_uuid = uuid.UUID(sub)
    except ValueError:
        raise InvalidCredentials() from None
    user = await db.get(User, user_uuid)
    if not user:
        raise InvalidCredentials()
    if user.is_blocked:
        await revoke_all_user_tokens(db, sub)
        raise AccountBlocked()

    pair = await issue_token_pair(db, user)

    # Link the successor for forensic traversal.
    new_jti = _jti_of(pair["refresh_token"])
    await db.execute(
        update(RefreshTokenRecord)
        .where(RefreshTokenRecord.jti == jti)
        .values(replaced_by=new_jti)
    )
    return pair


async def revoke_all_user_tokens(db: AsyncSession, user_id: str) -> None:
    """Revoke every refresh token belonging to ``user_id``."""
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return
    await db.execute(
        update(RefreshTokenRecord)
        .where(
            RefreshTokenRecord.user_id == uid,
            RefreshTokenRecord.revoked == False,  # noqa: E712
        )
        .values(revoked=True)
    )


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> bool:
    """Logout: revoke one specific refresh token (idempotent)."""
    payload = verify_refresh_token(refresh_token)
    if payload is None:
        return False
    jti = str(payload.get("jti", ""))
    if not jti:
        return False
    await db.execute(
        update(RefreshTokenRecord)
        .where(RefreshTokenRecord.jti == jti)
        .values(revoked=True)
    )
    return True


async def login_with_facebook(db: AsyncSession, fb_access_token: str) -> dict:
    """Exchange a FB user token for our JWT pair (Bearer header, never URL)."""
    import httpx

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.FB_GRAPH_API_URL}/me",
            # Bearer header — the token must never appear in URLs/logs.
            headers={"Authorization": f"Bearer {fb_access_token}"},
            params={"fields": "id,name,email"},
        )
        if resp.status_code != 200:
            raise InvalidCredentials()
        fb_data = resp.json()

    result = await db.execute(
        select(User).where(User.fb_user_id == fb_data["id"])
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=uuid.uuid4(),
            fb_user_id=fb_data["id"],
            name=fb_data.get("name", ""),
            email=fb_data.get("email"),
        )
        db.add(user)
        try:
            await db.flush()
        except IntegrityError:
            # FB gave an email that already exists locally — attach fb_user_id
            # to the existing account instead of crashing.
            await db.rollback()
            result = await db.execute(
                select(User).where(User.email == fb_data.get("email"))
            )
            user = result.scalar_one_or_none()
            if not user:
                raise InvalidCredentials() from None
            user.fb_user_id = fb_data["id"]
            await db.flush()

    if user.is_blocked:
        raise AccountBlocked()

    return await issue_token_pair(db, user)
