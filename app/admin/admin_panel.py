"""sqladmin configuration for the global admin panel.

The panel is mounted at ``/_admin`` and gated behind ``is_superadmin=True``
on the ``User`` model. Login flow:

  1. User visits ``/_admin/login``.
  2. Submits email + password.
  3. ``AdminAuth.login`` validates credentials via the existing
     ``auth_service.login_user`` (which returns a JWT) AND checks the
     loaded user has ``is_superadmin=True``.
  4. On success, the user's id is stashed in the Starlette session.
  5. ``AdminAuth.authenticate`` checks the session for that flag on every
     subsequent admin request.

The audit log view is append-only (no create/edit/delete) and the IPBan
view validates CIDR syntax on create.
"""
from __future__ import annotations

import ipaddress
import logging
import uuid
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from wtforms import ValidationError

from app.config import get_settings
from app.database import async_session
from app.models.admin import (
    AuditLog,
    IPBan,
    SiteUser,
    UserSession,
)
from app.models.user import User
from app.utils.security import verify_password

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------- #
# Authentication backend
# ---------------------------------------------------------------------- #
class AdminAuth(AuthenticationBackend):
    """sqladmin auth backend — gates access on ``User.is_superadmin``."""

    def __init__(self, secret_key: str | None = None) -> None:
        super().__init__(secret_key=secret_key or settings.JWT_SECRET_KEY)

    async def login(self, request: Request) -> bool:
        """Validate superadmin credentials and stash user id in session."""
        form = await request.form()
        email = form.get("username") or form.get("email")
        password = form.get("password")
        if not email or not password:
            return False

        async with async_session() as db:
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            if not user or not user.hashed_password:
                return False
            if not verify_password(password, user.hashed_password):
                return False
            if not user.is_superadmin:
                # Don't reveal that the account exists but isn't an admin.
                return False
            request.session.update({"_admin_user_id": str(user.id)})

        # Write audit entry
        await _write_audit(
            admin_id=user.id,
            action="admin_login",
            ip=request.client.host if request.client else None,
        )
        return True

    async def logout(self, request: Request) -> bool:
        user_id = request.session.get("_admin_user_id")
        if user_id:
            await _write_audit(
                admin_id=uuid.UUID(user_id),
                action="admin_logout",
                ip=request.client.host if request.client else None,
            )
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Response | bool:
        """Return True if session has a valid superadmin user id."""
        user_id = request.session.get("_admin_user_id")
        if not user_id:
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        try:
            uuid.UUID(user_id)
        except (ValueError, AttributeError):
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        return True


# ---------------------------------------------------------------------- #
# Audit helper (used by ModelView hooks too)
# ---------------------------------------------------------------------- #
async def _write_audit(
    *,
    admin_id: uuid.UUID,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    ip: Optional[str] = None,
) -> None:
    """Insert an audit-log row. Best-effort — never raises."""
    try:
        async with async_session() as db:
            db.add(
                AuditLog(
                    admin_id=admin_id,
                    action=action,
                    target_type=target_type,
                    target_id=str(target_id) if target_id else None,
                    metadata_=metadata,
                    ip=ip,
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to write audit log: %s", exc)


async def _current_admin_id(request: Request) -> Optional[uuid.UUID]:
    """Read the admin user id from the sqladmin session cookie."""
    raw = request.session.get("_admin_user_id")
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------- #
# ModelViews
# ---------------------------------------------------------------------- #
class BaseAdminView(ModelView):
    """Shared config — every admin view requires is_superadmin."""

    # Force the auth check at the page level too. sqladmin calls
    # ``is_accessible`` for navigation visibility; the AuthenticationBackend
    # above enforces the real gate on every request.

    def is_visible(self, request: Request) -> bool:  # noqa: D401
        return True

    def is_accessible(self, request: Request) -> bool:  # noqa: D401
        return bool(request.session.get("_admin_user_id"))


class UserAdmin(BaseAdminView, model=User):
    """User CRUD — admins can flip the ``is_superadmin`` flag here."""

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-users"

    column_list = [User.id, User.name, User.email, User.is_superadmin, User.created_at]
    column_searchable_list = [User.name, User.email]
    column_default_sort = ("created_at", True)

    form_columns = [User.name, User.email, User.hashed_password, User.is_superadmin]


class SiteUserAdmin(BaseAdminView, model=SiteUser):
    """Site-wide user record — blocking, last-seen, location."""

    name = "Site User"
    name_plural = "Site Users"
    icon = "fa-solid fa-user-shield"

    column_list = [
        SiteUser.id,
        SiteUser.user_id,
        SiteUser.is_blocked,
        SiteUser.last_country,
        SiteUser.last_device_type,
        SiteUser.last_seen,
    ]
    column_searchable_list = [SiteUser.last_country, SiteUser.last_city, SiteUser.last_ip]
    column_default_sort = ("last_seen", True)

    form_columns = [
        SiteUser.user_id,
        SiteUser.is_blocked,
        SiteUser.blocked_reason,
        SiteUser.last_ip,
        SiteUser.last_country,
        SiteUser.last_country_code,
        SiteUser.last_city,
        SiteUser.last_device_type,
    ]

    async def on_model_change(  # type: ignore[override]
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        admin_id = await _current_admin_id(request)
        if admin_id and is_created is False and "is_blocked" in data:
            # If the admin toggled the block flag, record blocker + reason.
            from datetime import datetime

            if data.get("is_blocked"):
                model.blocked_by = admin_id
                model.blocked_at = datetime.utcnow()
                await _write_audit(
                    admin_id=admin_id,
                    action="block_user",
                    target_type="site_user",
                    target_id=str(model.user_id),
                    metadata={"reason": data.get("blocked_reason")},
                    ip=request.client.host if request.client else None,
                )
            else:
                await _write_audit(
                    admin_id=admin_id,
                    action="unblock_user",
                    target_type="site_user",
                    target_id=str(model.user_id),
                    ip=request.client.host if request.client else None,
                )


class IPBanAdmin(BaseAdminView, model=IPBan):
    """IP ban list — supports both single IPs and CIDR ranges."""

    name = "IP Ban"
    name_plural = "IP Bans"
    icon = "fa-solid fa-ban"

    column_list = [IPBan.id, IPBan.ip_or_cidr, IPBan.reason, IPBan.created_at]
    column_searchable_list = [IPBan.ip_or_cidr]
    column_default_sort = ("created_at", True)

    form_columns = [IPBan.ip_or_cidr, IPBan.reason]

    async def on_model_change(  # type: ignore[override]
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        value = (data.get("ip_or_cidr") or "").strip()
        if not value:
            raise ValidationError({"ip_or_cidr": ["IP or CIDR is required."]})
        try:
            if "/" in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValidationError({"ip_or_cidr": [f"Invalid IP/CIDR: {exc}"]})

        admin_id = await _current_admin_id(request)
        if admin_id and is_created:
            model.banned_by = admin_id

    async def after_model_change(  # type: ignore[override]
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        # Invalidate the in-memory banlist cache so the new ban takes effect
        # immediately (no waiting for the 30s TTL).
        from app.middleware.security import IPBanMiddleware

        IPBanMiddleware.invalidate_all()

        admin_id = await _current_admin_id(request)
        if admin_id:
            await _write_audit(
                admin_id=admin_id,
                action="add_ip_ban" if is_created else "edit_ip_ban",
                target_type="ip_ban",
                target_id=str(model.id),
                metadata={"ip_or_cidr": model.ip_or_cidr},
                ip=request.client.host if request.client else None,
            )

    async def after_model_delete(  # type: ignore[override]
        self, model: Any, request: Request
    ) -> None:
        from app.middleware.security import IPBanMiddleware

        IPBanMiddleware.invalidate_all()
        admin_id = await _current_admin_id(request)
        if admin_id:
            await _write_audit(
                admin_id=admin_id,
                action="remove_ip_ban",
                target_type="ip_ban",
                target_id=str(model.id),
                metadata={"ip_or_cidr": model.ip_or_cidr},
                ip=request.client.host if request.client else None,
            )


class UserSessionAdmin(BaseAdminView, model=UserSession):
    """User session history — read-only at the UI level."""

    name = "User Session"
    name_plural = "User Sessions"
    icon = "fa-solid fa-clock-rotate-left"

    column_list = [
        UserSession.id,
        UserSession.user_id,
        UserSession.ip_address,
        UserSession.country,
        UserSession.device_type,
        UserSession.login_at,
        UserSession.is_active,
    ]
    column_searchable_list = [UserSession.ip_address, UserSession.country, UserSession.city]
    column_default_sort = ("login_at", True)

    can_create = False
    can_edit = False


class AuditLogAdmin(BaseAdminView, model=AuditLog):
    """Append-only audit log — no create/edit/delete."""

    name = "Audit Log"
    name_plural = "Audit Log"
    icon = "fa-solid fa-clipboard-list"

    column_list = [
        AuditLog.id,
        AuditLog.admin_id,
        AuditLog.action,
        AuditLog.target_type,
        AuditLog.target_id,
        AuditLog.ip,
        AuditLog.created_at,
    ]
    column_searchable_list = [AuditLog.action, AuditLog.target_id, AuditLog.ip]
    column_default_sort = ("created_at", True)

    can_create = False
    can_edit = False
    can_delete = False  # append-only — enforced at the UI level


# ---------------------------------------------------------------------- #
# Setup entry point
# ---------------------------------------------------------------------- #
def setup_admin(app, engine=None) -> Admin:
    """Mount the sqladmin panel onto ``app`` at ``/_admin``.

    Returns the ``Admin`` instance (so callers can register additional views
    or customise further).
    """
    admin = Admin(
        app,
        engine=engine,
        authentication_backend=AdminAuth(),
        base_url="/_admin",
        title="Zemest Admin",
    )
    admin.add_view(UserAdmin)
    admin.add_view(SiteUserAdmin)
    admin.add_view(IPBanAdmin)
    admin.add_view(UserSessionAdmin)
    admin.add_view(AuditLogAdmin)
    return admin


__all__ = [
    "AdminAuth",
    "UserAdmin",
    "SiteUserAdmin",
    "IPBanAdmin",
    "UserSessionAdmin",
    "AuditLogAdmin",
    "setup_admin",
]
