"""Custom admin dashboard route (HTML/JS at ``/_admin/dashboard``).

Serves a single-page dashboard that calls the REST API in
``app.admin.api`` for data. Must be registered BEFORE ``setup_admin``
so the route takes precedence over sqladmin's mount at ``/_admin``.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse

from app.admin.api import get_superadmin
from app.models.user import User

router = APIRouter(tags=["Admin Dashboard"], include_in_schema=False)

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"


@router.get("/_admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    admin: User = Depends(get_superadmin),
):
    """Render the custom admin dashboard.

    Auth is enforced via the ``get_superadmin`` dependency, which expects
    a Bearer JWT in the Authorization header. If the request has no token,
    the dependency returns 401 and the browser shows the JSON error —
    callers should redirect to the sqladmin login first.
    """
    if not _TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail="dashboard template missing")
    return HTMLResponse(_TEMPLATE_PATH.read_text(encoding="utf-8"))


@router.get("/_admin/dashboard-login", response_class=RedirectResponse, include_in_schema=False)
async def dashboard_login_redirect():
    """Convenience redirect: send dashboard visitors to sqladmin login."""
    return RedirectResponse(url="/_admin/login", status_code=302)


__all__ = ["router"]
