from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_tenant
from app.services import facebook_service

router = APIRouter(prefix="/api/facebook", tags=["Facebook"])


class ListPagesRequest(BaseModel):
    """Body model — the user token NEVER travels in the URL (audit A4-H2)."""

    fb_access_token: str = Field(..., min_length=20, max_length=2000)


class ConnectPageRequest(BaseModel):
    """Body model — the page token NEVER travels in the URL (audit A4-H2)."""

    page_id: str = Field(..., min_length=1, max_length=64)
    page_access_token: str = Field(..., min_length=20, max_length=2000)
    page_name: str = Field(..., min_length=1, max_length=255)


@router.post("/pages")
async def list_pages(
    req: ListPagesRequest,
    user=Depends(get_current_user),
):
    """List Facebook pages the user manages.

    POST + JSON body: the token stays out of query strings, proxies and
    access logs (was ``GET /pages?fb_access_token=EAAG…``).
    """
    pages = await facebook_service.get_user_pages(req.fb_access_token)
    return {"pages": pages}


@router.post("/connect")
async def connect_page(
    req: ConnectPageRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Facebook page to the platform.

    POST + JSON body (was query-string params on POST — FastAPI binds
    plain function params to the query string, so the Page token traveled
    in the URL even on POST).
    """
    from app.services.tenant_service import create_tenant

    # Subscribe to webhook
    success = await facebook_service.subscribe_page_to_webhook(
        req.page_id, req.page_access_token
    )
    if not success:
        raise HTTPException(
            status_code=400, detail="Failed to subscribe page to webhook"
        )

    tenant = await create_tenant(
        db,
        user,
        page_name=req.page_name,
        fb_page_id=req.page_id,
        page_access_token=req.page_access_token,
    )

    return {
        "message": "Page connected successfully",
        "tenant_id": str(tenant.id),
    }


@router.post("/{tenant_id}/sync-catalog")
async def sync_catalog(
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Sync products from Facebook page's product catalog."""
    if not tenant.page_access_token:
        raise HTTPException(status_code=400, detail="Page access token not set")

    products = await facebook_service.get_page_products(
        tenant.fb_page_id, tenant.page_access_token
    )

    from app.services.product_service import create_product

    imported = 0
    for p in products:
        try:
            price_str = p.get("price", "0")
            # FB price format: "100.00 EGP"
            price = price_str.split(" ")[0] if isinstance(price_str, str) else price_str

            await create_product(
                db,
                tenant.id,
                source="facebook",
                name=p.get("name", ""),
                description=p.get("description"),
                price=price,
                image_url=p.get("image_url"),
                source_ref=p.get("id"),
                stock_status="in_stock"
                if p.get("availability") == "in stock"
                else "out_of_stock",
            )
            imported += 1
        except ValueError:
            pass  # Duplicate, skip

    return {"message": f"Synced {imported} products from Facebook", "imported": imported}
