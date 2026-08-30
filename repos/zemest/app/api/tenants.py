import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_tenant
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate
from app.services import tenant_service

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


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
        payment_methods=t.payment_methods,
        order_api_config=t.order_api_config,
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
    updated = await tenant_service.update_tenant(
        db, tenant, **req.model_dump(exclude_none=True)
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
