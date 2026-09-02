import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_tenant
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate
from app.services import tenant_service

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


def _mask_secret(value: str | None) -> str | None:
    """Mask a secret for API responses (audit A3-M2).

    Returns ``"****last4"`` — enough for the merchant to recognize WHICH
    credential is stored, never the credential itself. Tokens/keys were
    previously echoed verbatim on every list/get, riding along into browser
    caches, BFF logs and anywhere the dashboard loads.
    """
    if not value:
        return value
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


def _mask_payment_methods(pm: dict | None) -> dict | None:
    """Mask wallet numbers / account IDs in payment_methods."""
    if not pm:
        return pm
    return {
        k: (_mask_secret(v) if isinstance(v, str) and v else v)
        for k, v in pm.items()
    }


def _mask_order_api_config(cfg: dict | None) -> dict | None:
    """Mask auth_value/auth_pass in order_api_config."""
    if not cfg:
        return cfg
    masked = dict(cfg)
    for key in ("auth_value", "auth_pass", "password", "token", "api_key"):
        if masked.get(key):
            masked[key] = "****"
    return masked


def _tenant_response(t) -> TenantResponse:
    return TenantResponse(
        id=str(t.id),
        fb_page_id=t.fb_page_id,
        page_name=t.page_name,
        website_url=t.website_url,
        business_phone=t.business_phone,
        business_email=t.business_email,
        notification_pref=t.notification_pref,
        delivery_inside_cairo=t.delivery_inside_cairo,
        delivery_outside_cairo=t.delivery_outside_cairo,
        free_delivery_above=t.free_delivery_above,
        payment_methods=_mask_payment_methods(t.payment_methods),
        order_api_config=_mask_order_api_config(t.order_api_config),
        is_active=t.is_active,
        created_at=t.created_at,
    )


@router.post("", response_model=TenantResponse)
async def create_tenant(
    req: TenantCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenant_service.create_tenant(
        db, user, **req.model_dump(),
    )
    return _tenant_response(tenant)


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenants = await tenant_service.get_user_tenants(db, user)
    return [_tenant_response(t) for t in tenants]


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant_detail(tenant=Depends(get_tenant)):
    return _tenant_response(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant_detail(
    req: TenantUpdate,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    # SSRF guard (audit A3-H1): validate the order_api_config webhook URL
    # at WRITE time so the retry-api endpoint can never be aimed at
    # internal/metadata endpoints later.
    if req.order_api_config is not None:
        cfg = req.order_api_config or {}
        if cfg.get("enabled"):
            url = cfg.get("url")
            if not url:
                raise HTTPException(422, "order_api_config.url is required when enabled")
            from app.middleware.ssrf_protection import is_safe_url
            safe, reason = is_safe_url(url)
            if not safe:
                raise HTTPException(422, f"order_api_config.url rejected: {reason}")
            method = (cfg.get("method") or "POST").upper()
            if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                raise HTTPException(422, f"order_api_config.method not allowed: {method}")

    # exclude_unset (not exclude_none): the settings page deliberately sends
    # nulls to CLEAR a field — exclude_none silently dropped them.
    updated = await tenant_service.update_tenant(
        db, tenant, **req.model_dump(exclude_unset=True)
    )
    return _tenant_response(updated)


@router.get("/{tenant_id}/stats")
async def get_stats(
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await tenant_service.get_tenant_stats(db, tenant.id)


# Note: rebuild-style endpoint is in app/api/style_learning.py
# (consolidated with the style-learning import flow)
