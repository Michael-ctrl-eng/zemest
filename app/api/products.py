from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant
from app.models.product import Product
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.services import product_service

router = APIRouter(prefix="/api/tenants/{tenant_id}/products", tags=["Products"])


def _product_to_response(p: Product) -> ProductResponse:
    return ProductResponse(
        id=str(p.id),
        name=p.name,
        price=p.price,
        is_active=p.is_active,
        source=p.source,
        created_at=p.created_at,
        attributes=p.attributes or {},
    )


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str | None = None,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    products, total = await product_service.get_products(
        db, tenant.id, page, page_size, search
    )
    return ProductListResponse(
        products=[_product_to_response(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    req: ProductCreate,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a product with any attributes.

    Only `name` and `price` are required. All other fields you send
    (description, category, color, size, brand, RAM, weight, etc.)
    are stored as flexible attributes. The AI agent will use whatever
    attributes you provide.
    """
    # Separate fixed fields from extra attributes
    data = req.model_dump()
    name = data.pop("name")
    price = data.pop("price")
    # Everything else the user sent becomes attributes
    attributes = data if data else None

    try:
        product = await product_service.create_product(
            db, tenant.id, name=name, price=price, attributes=attributes,
        )
        return _product_to_response(product)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Upload products from ANY CSV format.

    The system auto-detects name and price columns. All other columns
    are stored as product attributes automatically.

    Accepted name columns: name, product_name, title, item
    Accepted price columns: price, cost, amount, rate, mrp
    """
    content = (await file.read()).decode("utf-8")
    result = await product_service.import_csv(db, tenant.id, content)
    return result


@router.post("/import-url", response_model=ProductResponse, status_code=201)
async def import_from_url(
    req: dict,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Import a product by pasting its URL.

    The system crawls the page and extracts product details automatically.
    Tries JSON-LD → OG tags → HTML regex → LLM fallback.
    """
    url = req.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    from app.knowledge.product_extractor import extract_product_from_url
    from decimal import Decimal

    extracted = await extract_product_from_url(url)
    if not extracted or not extracted.get("name") or not extracted.get("price"):
        raise HTTPException(
            status_code=422,
            detail="Could not extract product from this URL. The page may be JS-rendered or have no product data.",
        )

    name = extracted.pop("name")
    price = Decimal(str(extracted.pop("price")))

    # Everything else becomes attributes
    attributes = {k: v for k, v in extracted.items() if v}

    try:
        product = await product_service.create_product(
            db, tenant.id,
            name=name,
            price=price,
            source="url",
            source_ref=url,
            attributes=attributes,
        )
        return _product_to_response(product)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.tenant_id == tenant.id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_to_response(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    req: ProductUpdate,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.tenant_id == tenant.id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    updated = await product_service.update_product(
        db, product, **req.model_dump(exclude_none=True)
    )
    return _product_to_response(updated)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.tenant_id == tenant.id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await product_service.delete_product(db, product)
