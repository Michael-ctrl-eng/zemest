import uuid
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.dependencies import get_tenant
from app.models.crawl_job import CrawlJob
from app.schemas.webhook import CrawlRequest, CrawlJobResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}/crawl", tags=["Crawling"])


@router.post("", response_model=CrawlJobResponse, status_code=201)
async def start_crawl(
    req: CrawlRequest,
    background_tasks: BackgroundTasks,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    job = CrawlJob(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        url=req.url,
        status="pending",
    )
    db.add(job)
    await db.flush()

    job_id = str(job.id)
    tenant_id = str(tenant.id)

    # Try Celery first (only if a worker is actually running), fallback to BackgroundTasks
    celery_dispatched = False
    try:
        from app.tasks.celery_app import celery_app
        # Ping workers with short timeout — if no worker responds, use fallback
        inspect = celery_app.control.inspect(timeout=1)
        try:
            active_workers = inspect.ping()
        except Exception as ping_err:
            logger.debug(f"Celery ping failed: {ping_err}")
            active_workers = None
        if active_workers:
            from app.tasks.crawl_tasks import run_crawl_pipeline
            task = run_crawl_pipeline.delay(job_id, tenant_id, req.url, req.depth)
            job.celery_task_id = task.id
            await db.flush()
            celery_dispatched = True
            logger.info(f"Crawl job {job_id} dispatched to Celery worker")
        else:
            logger.info("No Celery workers found, using BackgroundTasks")
    except Exception as e:
        logger.warning(f"Celery unavailable ({e}), using BackgroundTasks fallback")

    if not celery_dispatched:
        # Run inline via FastAPI BackgroundTasks
        background_tasks.add_task(
            _run_crawl_inline, job_id, tenant_id, req.url, req.depth
        )
        logger.info(f"Crawl job {job_id} dispatched to BackgroundTasks")

    return CrawlJobResponse(
        id=job_id,
        url=job.url,
        status=job.status,
        pages_found=job.pages_found,
        products_extracted=job.products_extracted,
        error_message=job.error_message,
        created_at=str(job.created_at),
    )


async def _run_crawl_inline(job_id: str, tenant_id: str, url: str, depth: int):
    """Run crawl pipeline directly (when Celery is not available)."""
    from datetime import datetime
    from decimal import Decimal
    from app.knowledge.crawler import crawl_website
    from app.knowledge.indexer import build_knowledge_index
    from app.ai.llm_client import chat_completion
    from app.services.product_service import create_product
    import json
    import re

    async with async_session() as db:
        job = await db.get(CrawlJob, uuid.UUID(job_id))
        if not job:
            return

        try:
            # Crawling
            job.status = "crawling"
            job.started_at = datetime.utcnow()
            await db.commit()

            pages = await crawl_website(url, depth)
            job.pages_found = len(pages)
            await db.commit()

            if not pages:
                job.status = "failed"
                job.error_message = "No pages found — site may be blocking crawlers or has no content"
                job.completed_at = datetime.utcnow()
                await db.commit()
                return

            # Indexing — build knowledge base
            job.status = "indexing"
            await db.commit()

            await build_knowledge_index(db, uuid.UUID(tenant_id), pages)

            # Extract products using LLM
            products_count = await _extract_products_from_pages(
                db, uuid.UUID(tenant_id), pages
            )
            job.products_extracted = products_count

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            await db.commit()

            logger.info(f"Crawl done: {url} → {len(pages)} pages, {products_count} products")

        except Exception as e:
            logger.error(f"Crawl failed for {url}: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)[:500]
            job.completed_at = datetime.utcnow()
            await db.commit()


async def _extract_products_from_pages(
    db, tenant_id: uuid.UUID, pages: list[dict]
) -> int:
    """Use LLM to extract products from crawled page content."""
    from app.ai.llm_client import chat_completion
    from app.services.product_service import create_product
    from decimal import Decimal
    import json
    import re

    all_content = "\n\n---\n\n".join(
        f"Page URL: {p.get('url', '')}\nPage: {p.get('title', '')}\n{p.get('content', '')[:2000]}"
        for p in pages[:20]
    )

    prompt = f"""Extract all products from this website content.

For each product, extract:
- "name" (required): product name
- "price" (required): numeric price (just the number, no currency symbol)
- "url" (if available): the product page URL from "Page URL" above
- "description": product description, quality details, specifications — be detailed
- Any other relevant attributes (category, color, size, weight, brand, material, flavor, ingredients, etc.)

IMPORTANT: Include rich descriptions with quality details — anything that helps sell the product.
Return as a JSON array. If no products found, return an empty array [].

Website content:
{all_content[:6000]}"""

    try:
        logger.info(f"Sending {len(all_content)} chars to LLM for product extraction...")
        from app.ai.llm_client import chat_completion_with_usage
        from app.models.token_usage import TokenUsage
        llm_result = await chat_completion_with_usage(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=3000,
        )
        response = llm_result.content
        logger.info(f"LLM response ({len(response)} chars): {response[:200]}...")

        # Track crawl token usage
        usage = TokenUsage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            usage_type="crawl",
            model=llm_result.model,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
        )
        db.add(usage)
        await db.flush()

        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if not json_match:
            logger.warning("No JSON array found in LLM response")
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
                attributes = {k: v for k, v in p.items() if v is not None}

                product_url = attributes.get("url", "")
                source_ref = product_url if product_url else f"{base_url}#product-{i}"

                await create_product(
                    db, tenant_id,
                    name=name, price=price,
                    source="crawl",
                    source_ref=source_ref,
                    attributes=attributes if attributes else None,
                )
                count += 1
            except Exception:
                await db.rollback()

        return count

    except Exception as e:
        logger.error(f"Product extraction failed: {e}")
        return 0


@router.get("/jobs", response_model=list[CrawlJobResponse])
async def list_crawl_jobs(
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.tenant_id == tenant.id)
        .order_by(CrawlJob.created_at.desc())
        .limit(20)
    )
    jobs = result.scalars().all()
    return [
        CrawlJobResponse(
            id=str(j.id), url=j.url, status=j.status,
            pages_found=j.pages_found, products_extracted=j.products_extracted,
            error_message=j.error_message, created_at=str(j.created_at),
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=CrawlJobResponse)
async def get_crawl_job(
    job_id: uuid.UUID,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.tenant_id == tenant.id
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return CrawlJobResponse(
        id=str(job.id), url=job.url, status=job.status,
        pages_found=job.pages_found, products_extracted=job.products_extracted,
        error_message=job.error_message, created_at=str(job.created_at),
    )
