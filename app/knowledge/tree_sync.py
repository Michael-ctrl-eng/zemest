"""Sync products from DB into the PageIndex tree.

When products are added/edited/deleted, this rebuilds the product
section of the tree. Zero LLM cost — just formats data from DB.

Tree structure:
  root
  ├── [Products]
  │   ├── Category: Honey
  │   │   ├── Sundarban Honey 1kg — 2200 EGP ✅
  │   │   ├── Crystal Honey 1kg — 1000 EGP ✅
  │   │   └── ...
  │   ├── Category: Dates
  │   │   └── ...
  │   └── Uncategorized
  │       └── ...
  └── [Knowledge] (from website crawl — unchanged)
      ├── About Us
      ├── Delivery Policy
      └── ...
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.models.product import Product

logger = logging.getLogger(__name__)


async def rebuild_product_tree(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Rebuild the product section of the PageIndex tree from the products table.

    Zero LLM cost — purely formats DB data into tree nodes.
    Preserves existing knowledge nodes from website crawl.
    """
    # Get all active products
    result = await db.execute(
        select(Product)
        .where(Product.tenant_id == tenant_id, Product.is_active == True)
        .order_by(Product.name)
    )
    products = result.scalars().all()

    # Build product tree nodes grouped by category
    product_nodes = _build_product_nodes(products)

    # Get existing knowledge base
    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
    )
    kb = kb_result.scalar_one_or_none()

    if kb and kb.tree_json:
        # Preserve knowledge nodes, replace product nodes
        _merge_into_tree(kb, product_nodes)
    else:
        # No KB exists — create one with just products
        tree_data = {
            "type": "pageindex",
            "tree": {
                "doc_name": "business_catalog",
                "structure": product_nodes,
            },
            "metadata": {
                "indexed_at": datetime.utcnow().isoformat(),
                "products_count": len(products),
            },
        }
        kb = KnowledgeBase(
            tenant_id=tenant_id,
            tree_json=tree_data,
            source_documents=[],
            last_indexed_at=datetime.utcnow(),
        )
        db.add(kb)

    await db.flush()
    logger.info(f"Product tree rebuilt: {len(products)} products in {len(product_nodes)} nodes")


def _build_product_nodes(products: list[Product]) -> list[dict]:
    """Convert products into PageIndex tree nodes grouped by category."""
    # Group by category
    categories = {}
    for p in products:
        attrs = p.attributes or {}
        cat = attrs.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)

    nodes = []
    node_id = 1

    for cat_name, cat_products in sorted(categories.items()):
        # Category node
        child_nodes = []
        for p in cat_products:
            attrs = p.attributes or {}
            stock = attrs.get("stock_status", "in_stock")
            stock_icon = {"in_stock": "✅", "out_of_stock": "❌", "limited": "⚠️"}.get(stock, "📦")

            # Build rich text for this product
            lines = [f"# {p.name}"]
            if attrs.get("name_ar"):
                lines.append(f"Arabic: {attrs['name_ar']}")
            lines.append(f"Price: {p.price} EGP")
            if attrs.get("discount_price"):
                lines.append(f"Discount Price: {attrs['discount_price']} EGP")
            lines.append(f"Stock: {stock_icon} {stock}")
            if attrs.get("description"):
                lines.append(f"Description: {attrs['description']}")
            if attrs.get("url"):
                lines.append(f"PRODUCT LINK (share with customer): {attrs['url']}")

            # Add all other attributes
            skip = {"name_ar", "category", "stock_status", "description",
                    "discount_price", "image_url", "url", "sku", "brand"}
            for k, v in attrs.items():
                if k not in skip and v is not None and v != "":
                    lines.append(f"{k}: {v}")

            text = "\n".join(lines)

            child_nodes.append({
                "title": f"{p.name} — {p.price} EGP {stock_icon}",
                "node_id": str(node_id).zfill(4),
                "text": text,
                "line_num": node_id,
                "summary": f"{p.name}, {p.price} EGP, {stock}. {(attrs.get('description') or '')[:100]}",
                "_product_id": str(p.id),
                "_type": "product",
            })
            node_id += 1

        # Category parent node
        cat_summary = ", ".join(p.name for p in cat_products[:5])
        if len(cat_products) > 5:
            cat_summary += f"... (+{len(cat_products)-5} more)"

        cat_node = {
            "title": f"{cat_name} ({len(cat_products)} products)",
            "node_id": str(node_id).zfill(4),
            "text": f"Category: {cat_name}\nProducts: {cat_summary}",
            "line_num": node_id,
            "summary": f"{cat_name} category with {len(cat_products)} products: {cat_summary}",
            "nodes": child_nodes,
            "_type": "product_category",
        }
        node_id += 1
        nodes.append(cat_node)

    return nodes


def _merge_into_tree(kb: KnowledgeBase, product_nodes: list[dict]) -> None:
    """Replace product nodes in existing tree, keep knowledge nodes."""
    storage = kb.tree_json or {}

    if storage.get("type") == "pageindex":
        tree = storage.get("tree", {})
        structure = tree.get("structure", [])
    else:
        structure = storage.get("children", storage.get("structure", []))

    # Separate knowledge nodes from product nodes
    knowledge_nodes = [
        n for n in structure
        if n.get("_type") not in ("product", "product_category")
    ]

    # Merge: products first, then knowledge
    new_structure = product_nodes + knowledge_nodes

    # Reassign node IDs
    _reassign_ids(new_structure)

    # Update storage
    if storage.get("type") == "pageindex":
        storage["tree"]["structure"] = new_structure
        storage["metadata"]["products_count"] = sum(
            len(n.get("nodes", [])) for n in product_nodes
        )
        storage["metadata"]["last_product_sync"] = datetime.utcnow().isoformat()
    else:
        storage["children"] = new_structure

    kb.tree_json = storage
    kb.last_indexed_at = datetime.utcnow()


def _reassign_ids(nodes: list[dict], start: int = 1) -> int:
    """Reassign sequential node IDs after merge."""
    current = start
    for node in nodes:
        node["node_id"] = str(current).zfill(4)
        node["line_num"] = current
        current += 1
        children = node.get("nodes", [])
        if children:
            current = _reassign_ids(children, current)
    return current
