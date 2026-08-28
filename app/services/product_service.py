from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


async def create_product(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    price: Decimal,
    source: str = "manual",
    source_ref: str | None = None,
    attributes: dict | None = None,
) -> Product:
    """Create a product with flexible attributes."""
    # Check for duplicates before creating
    sku = (attributes or {}).get("sku")
    await _check_duplicate(db, tenant_id, name, sku)

    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        price=price,
        source=source,
        source_ref=source_ref,
        attributes=attributes or {},
    )
    db.add(product)
    await db.flush()

    # Sync product tree (zero LLM cost)
    await _sync_product_tree(db, tenant_id)

    return product


async def _check_duplicate(
    db: AsyncSession, tenant_id: uuid.UUID, name: str, sku: str | None = None
) -> None:
    """Check for duplicate products using fuzzy name matching and SKU."""
    # SKU exact match (check inside attributes JSON)
    if sku:
        result = await db.execute(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.is_active == True,
            )
        )
        existing = result.scalars().all()
        for p in existing:
            if p.attributes and p.attributes.get("sku") == sku:
                raise ValueError(f"Product with SKU '{sku}' already exists")

    # Fuzzy name match using pg_trgm (PostgreSQL only)
    if name:
        try:
            result = await db.execute(
                text(
                    "SELECT id, name, similarity(name, :name) as sim "
                    "FROM products "
                    "WHERE tenant_id = :tenant_id AND is_active = true "
                    "AND similarity(name, :name) > 0.7 "
                    "ORDER BY sim DESC LIMIT 1"
                ),
                {"tenant_id": str(tenant_id), "name": name},
            )
            row = result.first()
            if row:
                raise ValueError(
                    f"Similar product already exists: '{row.name}' (similarity: {row.sim:.0%})"
                )
        except Exception as e:
            if "similarity" in str(e).lower() or "no such function" in str(e).lower():
                result = await db.execute(
                    select(Product).where(
                        Product.tenant_id == tenant_id,
                        Product.name == name,
                        Product.is_active == True,
                    )
                )
                if result.scalar_one_or_none():
                    raise ValueError(f"Product with name '{name}' already exists")
            else:
                raise


async def get_products(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> tuple[list[Product], int]:
    query = select(Product).where(
        Product.tenant_id == tenant_id, Product.is_active == True
    )
    count_query = select(func.count(Product.id)).where(
        Product.tenant_id == tenant_id, Product.is_active == True
    )

    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
        count_query = count_query.where(Product.name.ilike(f"%{search}%"))

    total = await db.scalar(count_query) or 0
    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size).order_by(Product.created_at.desc())
    )
    return list(result.scalars().all()), total


async def update_product(db: AsyncSession, product: Product, **kwargs) -> Product:
    """Update product — fixed fields are set directly, extras merge into attributes."""
    fixed_fields = {"name", "price", "is_active", "source", "source_ref"}
    new_attrs = dict(product.attributes or {})

    for key, value in kwargs.items():
        if value is None:
            continue
        if key in fixed_fields:
            setattr(product, key, value)
        elif key == "attributes" and isinstance(value, dict):
            new_attrs.update(value)
        else:
            new_attrs[key] = value

    product.attributes = new_attrs
    await db.flush()

    # Sync product tree (zero LLM cost)
    await _sync_product_tree(db, product.tenant_id)

    return product


async def delete_product(db: AsyncSession, product: Product) -> None:
    product.is_active = False
    await db.flush()

    # Sync product tree (zero LLM cost)
    await _sync_product_tree(db, product.tenant_id)


async def import_csv(
    db: AsyncSession, tenant_id: uuid.UUID, file_content: str
) -> dict:
    """Import products from ANY CSV format.

    Rules:
    - Must have a column that looks like a product name (name, product_name, title, item, etc.)
    - Must have a column that looks like a price (price, cost, amount, rate, etc.)
    - ALL other columns are stored as attributes automatically
    """
    reader = csv.DictReader(io.StringIO(file_content))
    if not reader.fieldnames:
        return {"imported": 0, "skipped": 0, "errors": ["Empty CSV or no headers"]}

    # Auto-detect name and price columns
    columns = [c.strip().lower() for c in reader.fieldnames]
    name_col = _find_column(columns, reader.fieldnames, ["name", "product_name", "product", "title", "item", "item_name"])
    price_col = _find_column(columns, reader.fieldnames, ["price", "cost", "amount", "rate", "mrp", "unit_price"])

    if not name_col:
        return {"imported": 0, "skipped": 0, "errors": ["No name column found. Use: name, product_name, title, or item"]}
    if not price_col:
        return {"imported": 0, "skipped": 0, "errors": ["No price column found. Use: price, cost, amount, or rate"]}

    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        try:
            name = row.get(name_col, "").strip()
            if not name:
                errors.append(f"Row {i}: Missing product name")
                continue

            price_str = row.get(price_col, "0").strip().replace(",", "").replace("EGP", "").replace("ج.م", "").replace("$", "")
            try:
                price = Decimal(price_str)
            except Exception:
                errors.append(f"Row {i}: Invalid price '{row.get(price_col, '')}'")
                continue

            if price <= 0:
                errors.append(f"Row {i}: Price must be positive")
                continue

            # Everything else becomes attributes
            attributes = {}
            for col_name in reader.fieldnames:
                if col_name in (name_col, price_col):
                    continue
                val = row.get(col_name, "").strip()
                if val:
                    # Try to parse numbers and booleans
                    attributes[col_name] = _parse_value(val)

            try:
                await create_product(
                    db, tenant_id,
                    name=name,
                    price=price,
                    source="csv",
                    attributes=attributes if attributes else None,
                )
                imported += 1
            except ValueError as e:
                skipped += 1
                errors.append(f"Row {i}: {e}")

        except Exception as e:
            errors.append(f"Row {i}: Unexpected error - {e}")

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "detected_columns": {
            "name_column": name_col,
            "price_column": price_col,
            "attribute_columns": [c for c in reader.fieldnames if c not in (name_col, price_col)],
        },
    }


def _find_column(lower_columns: list[str], original_columns: list[str], candidates: list[str]) -> str | None:
    """Find a column by checking against candidate names."""
    for candidate in candidates:
        for i, col in enumerate(lower_columns):
            if col == candidate:
                return original_columns[i]
    return None


def _parse_value(val: str):
    """Try to parse a string value into its natural type."""
    if val.lower() in ("true", "yes", "نعم", "أيوه"):
        return True
    if val.lower() in ("false", "no", "لا"):
        return False
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        return val


async def get_all_products_for_context(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[dict]:
    """Get all active products as flat dicts for AI context."""
    result = await db.execute(
        select(Product)
        .where(Product.tenant_id == tenant_id, Product.is_active == True)
        .order_by(Product.name)
    )
    products = result.scalars().all()
    return [p.to_dict() for p in products]


async def search_relevant_products(
    db: AsyncSession, tenant_id: uuid.UUID, query: str, max_results: int = 8
) -> list[dict]:
    """Search products relevant to customer query. Zero LLM cost.

    Returns at most max_results products to keep the prompt small.
    If fewer than max_results total products exist, returns all.
    """
    import re
    from difflib import SequenceMatcher

    result = await db.execute(
        select(Product)
        .where(Product.tenant_id == tenant_id, Product.is_active == True)
    )
    all_products = result.scalars().all()

    if not all_products:
        return []

    # If few products, return all — no need to filter
    if len(all_products) <= max_results:
        return [p.to_dict() for p in all_products]

    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))

    # Words that don't help find products (Egyptian Arabic + English stopwords)
    stop_words = {
        "hi", "hello", "hey", "ya", "eh", "aib", "fee", "and", "price",
        "siir", "order", "ayz", "3ayz", "3awz", "gamed", "gez", "show",
        "list", "all", "products", "product", "please", "ana",
        "enta", "enti", "enta", "3andi", "3andak", "3andik", "el", "del",
        "the", "a", "is", "what", "how", "can", "do", "you", "i", "me", "my",
        "ezay", "kam", "shno", "ana", "eh", "feen", "men", "fain", "3al",
        "we", "w", "b", "el", "del", "dh", "dh", "3", "fe", "men",
    }
    meaningful = query_words - stop_words

    scored = []
    for p in all_products:
        pd = p.to_dict()
        name_lower = p.name.lower()
        attrs = p.attributes or {}
        desc = (attrs.get("description", "") or "").lower()
        category = (attrs.get("category", "") or "").lower()
        all_text = f"{name_lower} {desc} {category}"
        all_words = set(re.findall(r'\w+', all_text))

        if meaningful:
            overlap = len(meaningful & all_words)
            name_match = 3 if any(w in name_lower for w in meaningful) else 0
            name_sim = SequenceMatcher(None, query_lower, name_lower).ratio()
            score = overlap * 3 + name_match + name_sim
        else:
            score = 0

        scored.append((score, pd))

    scored.sort(key=lambda x: x[0], reverse=True)

    # If generic query (no meaningful words), return diverse sample
    if not meaningful:
        seen_cats = set()
        diverse = []
        for _, pd in scored:
            cat = (pd.get("category") or "general")
            if cat not in seen_cats:
                diverse.append(pd)
                seen_cats.add(cat)
            if len(diverse) >= max_results:
                break
        # Fill remaining slots
        for _, pd in scored:
            if pd not in diverse:
                diverse.append(pd)
            if len(diverse) >= max_results:
                break
        return diverse

    return [pd for _, pd in scored[:max_results]]


async def _sync_product_tree(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Rebuild the product section of PageIndex tree. Zero LLM cost."""
    try:
        from app.knowledge.tree_sync import rebuild_product_tree
        await rebuild_product_tree(db, tenant_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Product tree sync failed: {e}")
