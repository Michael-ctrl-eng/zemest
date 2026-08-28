from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_tenant
from app.services import facebook_service

router = APIRouter(prefix="/api/facebook", tags=["Facebook"])


@router.get("/pages")
async def list_pages(
    fb_access_token: str,
    user=Depends(get_current_user),
):
    """List Facebook pages the user manages."""
    pages = await facebook_service.get_user_pages(fb_access_token)
    return {"pages": pages}


@router.post("/connect")
async def connect_page(
    page_id: str,
    page_access_token: str,
    page_name: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Facebook page to the platform."""
    from app.services.tenant_service import create_tenant

    # Subscribe to webhook
    success = await facebook_service.subscribe_page_to_webhook(
        page_id, page_access_token
    )
    if not success:
        raise HTTPException(
            status_code=400, detail="Failed to subscribe page to webhook"
        )

    tenant = await create_tenant(
        db,
        user,
        page_name=page_name,
        fb_page_id=page_id,
        page_access_token=page_access_token,
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
