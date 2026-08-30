import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code in Celery synchronous tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=2)
def run_crawl_pipeline(self, job_id: str, tenant_id: str, url: str, depth: int = 3):
    """Full crawl pipeline: crawl -> extract products -> build knowledge index."""
    _run_async(_crawl_pipeline_async(job_id, tenant_id, url, depth))


async def _crawl_pipeline_async(job_id: str, tenant_id: str, url: str, depth: int):
    from app.database import async_session
    from app.models.crawl_job import CrawlJob
    from app.knowledge.crawler import crawl_website
    from app.knowledge.indexer import build_knowledge_index

    async with async_session() as db:
        # Get job
        job = await db.get(CrawlJob, uuid.UUID(job_id))
        if not job:
            return

        try:
            # Update status
            job.status = "crawling"
            job.started_at = datetime.utcnow()
            await db.commit()

            # Crawl website
            pages = await crawl_website(url, depth)
            job.pages_found = len(pages)
            await db.commit()

            if not pages:
                job.status = "failed"
                job.error_message = "No pages found to crawl"
                job.completed_at = datetime.utcnow()
                await db.commit()
                return

            # Extract products from crawled content
            job.status = "indexing"
            await db.commit()

            products_count = await _extract_and_save_products(
                db, uuid.UUID(tenant_id), pages
            )
            job.products_extracted = products_count

            # Build knowledge index
            await build_knowledge_index(db, uuid.UUID(tenant_id), pages)

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            await db.commit()

            logger.info(
                f"Crawl completed for {url}: "
                f"{len(pages)} pages, {products_count} products"
            )

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)[:500]
            job.completed_at = datetime.utcnow()
            await db.commit()
            logger.error(f"Crawl pipeline failed: {e}", exc_info=True)


async def _extract_and_save_products(db, tenant_id: uuid.UUID, pages: list[dict]) -> int:
    """Use LLM to extract product data from crawled pages."""
    from app.ai.llm_client import chat_completion
    from app.services.product_service import create_product
    import json
    import re

    # Build page content with URLs preserved for product URL extraction
    all_content = "\n\n---\n\n".join(
        f"Page URL: {p.get('url', '')}\nPage: {p.get('title', '')}\n{p.get('content', '')[:2000]}"
        for p in pages[:20]
    )

    # Build a URL lookup — map product names/titles to their page URLs
    page_urls = [p.get("url", "") for p in pages[:20]]

    prompt = f"""Extract all products from this website content.

For each product, extract:
- "name" (required): product name
- "price" (required): numeric price (just the number, no currency symbol)
- "url" (if available): the product page URL from the "Page URL" above where this product was found
- "description": product description, quality details, specifications — be detailed
- Any other relevant attributes you find (category, color, size, weight, brand, material, flavor, ingredients, specs, etc.)

IMPORTANT: Include rich descriptions with quality details, ingredients, specifications — anything that helps sell the product.

Return as a JSON array. Include ALL attributes you can find for each product.

If no products found, return an empty array [].

Website content:
{all_content[:6000]}"""

    try:
        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=3000,
        )

        # Parse JSON from response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if not json_match:
            return 0

        products = json.loads(json_match.group())
        count = 0
        base_url = pages[0].get("url", "") if pages else ""

        for i, p in enumerate(products):
            try:
                price = Decimal(str(p.get("price", 0)))
                if price <= 0:
                    continue

                name = p.pop("name", "Unknown Product")
                p.pop("price", None)
                # Everything else becomes attributes
                attributes = {k: v for k, v in p.items() if v is not None}

                # Use actual product URL as source_ref if available, else generate unique one
                product_url = attributes.get("url", "")
                source_ref = product_url if product_url else f"{base_url}#product-{i}"

                await create_product(
                    db,
                    tenant_id,
                    name=name,
                    price=price,
                    source="crawl",
                    source_ref=source_ref,
                    attributes=attributes if attributes else None,
                )
                await db.commit()
                count += 1
                logger.info(f"Saved product: {name} {price} EGP")
            except Exception as e:
                await db.rollback()
                logger.warning(f"Skipped product '{p.get('name', '?')}': {e}")

        return count

    except Exception as e:
        logger.error(f"Product extraction failed: {e}")
        return 0
