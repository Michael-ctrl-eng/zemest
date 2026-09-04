"""Blog + SEO module — tenant-scoped CRUD, public blog, sitemap, robots.

Merchant API (auth, tenant-scoped):
- POST   /api/tenants/{id}/blog/posts          — create draft (blocks)
- GET    /api/tenants/{id}/blog/posts          — list (drafts + published)
- GET    /api/tenants/{id}/blog/posts/{pid}    — read + SEO checks detail
- PATCH  /api/tenants/{id}/blog/posts/{pid}    — edit blocks/meta
- POST   /api/tenants/{id}/blog/posts/{pid}/publish   — publish (SEO gate)
- POST   /api/tenants/{id}/blog/posts/{pid}/unpublish — back to draft
- DELETE /api/tenants/{id}/blog/posts/{pid}    — remove
- POST   /api/tenants/{id}/blog/generate       — AI draft from topic

Public (no auth):
- GET /blog                — published posts across shops (latest first)
- GET /blog/{slug}         — rendered post (escaped HTML)
- GET /sitemap.xml         — published posts + shop home pages
- GET /robots.txt          — allows /, /blog; blocks /api, /dashboard

Plan gating: blog is a Growth+ feature (see blog_plan_guard).
"""
from __future__ import annotations

import logging
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, get_tenant
from app.models.blog_post import BlogPost
from app.models.tenant import Tenant
from app.models.user import User
from app.services import blog_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}/blog", tags=["Blog"])
public_router = APIRouter(tags=["Blog (public)"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BlockModel(BaseModel):
    type: str = Field(..., pattern="^(heading|paragraph|image|quote)$")
    text: str | None = Field(None, max_length=10_000)
    level: int | None = Field(None, ge=2, le=4)
    url: str | None = Field(None, max_length=512)
    alt: str | None = Field(None, max_length=300)
    cite: str | None = Field(None, max_length=200)


class BlogPostCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    slug: str | None = Field(None, max_length=200)
    keyword: str | None = Field(None, max_length=100)
    meta_description: str | None = Field(None, max_length=300)
    cover_image_url: str | None = Field(None, max_length=512)
    blocks: list[BlockModel] = Field(default_factory=list, max_length=200)


class BlogPostUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    slug: str | None = Field(None, max_length=200)
    keyword: str | None = Field(None, max_length=100)
    meta_description: str | None = Field(None, max_length=300)
    cover_image_url: str | None = Field(None, max_length=512)
    blocks: list[BlockModel] | None = None


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=300)


def _serialize(post: BlogPost, checks: list[dict] | None = None) -> dict:
    data = {
        "id": str(post.id),
        "slug": post.slug,
        "title": post.title,
        "keyword": post.keyword,
        "meta_description": post.meta_description,
        "cover_image_url": post.cover_image_url,
        "blocks": post.blocks or [],
        "status": post.status,
        "seo_score": post.seo_score,
        "word_count": post.word_count,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
    }
    if checks is not None:
        data["seo_checks"] = checks
    return data


async def _get_post_or_404(db: AsyncSession, tenant: Tenant, post_id: str) -> BlogPost:
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(404, "Post not found")
    result = await db.execute(
        select(BlogPost).where(BlogPost.id == post_uuid, BlogPost.tenant_id == tenant.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    return post


def _blog_plan_guard(tenant: Tenant, owner: User) -> None:
    """Blog + SEO toolkit is a Growth+ feature (see plan catalog).

    Trial-aware: a user inside their 7-day trial enjoys Growth features.
    """
    from app.services.plan_service import PlanLimitError, get_limits_for_user
    limits = get_limits_for_user(owner)
    if "Blog + SEO toolkit" not in limits.features:
        raise HTTPException(
            402,
            detail={
                "code": "blog_feature",
                "message": (
                    "The Blog + SEO toolkit is part of the Growth plan. "
                    "Upgrade to publish SEO content that ranks."
                ),
                "plan": limits.key,
                "upgrade_url": "/api/plans",
            },
        )


# ---------------------------------------------------------------------------
# Merchant CRUD
# ---------------------------------------------------------------------------

@router.post("/posts")
async def create_blog_post(
    req: BlogPostCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _blog_plan_guard(tenant, user)
    try:
        post = await blog_service.create_post(
            db, tenant.id,
            title=req.title, slug=req.slug, keyword=req.keyword,
            meta_description=req.meta_description,
            cover_image_url=req.cover_image_url,
            blocks=[b.model_dump(exclude_none=True) for b in req.blocks],
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    score, checks = blog_service.score_seo(post)
    return _serialize(post, checks)


@router.get("/posts")
async def list_blog_posts(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BlogPost)
        .where(BlogPost.tenant_id == tenant.id)
        .order_by(BlogPost.updated_at.desc())
    )
    return {"posts": [_serialize(p) for p in result.scalars().all()]}


@router.get("/posts/{post_id}")
async def get_blog_post(
    post_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    post = await _get_post_or_404(db, tenant, post_id)
    score, checks = blog_service.score_seo(post)
    return _serialize(post, checks)


@router.patch("/posts/{post_id}")
async def update_blog_post(
    post_id: str,
    req: BlogPostUpdate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    post = await _get_post_or_404(db, tenant, post_id)
    kwargs = req.model_dump(exclude_unset=True, exclude_none=False)
    if "blocks" in kwargs and kwargs["blocks"] is not None:
        kwargs["blocks"] = [b for b in kwargs["blocks"]]
    try:
        post = await blog_service.update_post(db, post, **kwargs)
    except ValueError as e:
        raise HTTPException(422, str(e))
    score, checks = blog_service.score_seo(post)
    return _serialize(post, checks)


@router.post("/posts/{post_id}/publish")
async def publish_blog_post(
    post_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _blog_plan_guard(tenant, user)
    post = await _get_post_or_404(db, tenant, post_id)
    try:
        post = await blog_service.publish(db, post)
    except ValueError as e:
        raise HTTPException(422, str(e))
    score, checks = blog_service.score_seo(post)
    return _serialize(post, checks)


@router.post("/posts/{post_id}/unpublish")
async def unpublish_blog_post(
    post_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    post = await _get_post_or_404(db, tenant, post_id)
    post = await blog_service.update_post(db, post, status="draft")
    return _serialize(post)


@router.delete("/posts/{post_id}")
async def delete_blog_post(
    post_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    post = await _get_post_or_404(db, tenant, post_id)
    await db.delete(post)
    await db.commit()
    return {"deleted": True}


@router.post("/generate")
async def generate_blog_draft(
    req: GenerateRequest,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI writer: generate a draft from a topic (trend research / product
    line). Falls back honestly when no LLM is available."""
    _blog_plan_guard(tenant, user)
    draft = await blog_service.generate_draft(req.topic, tenant)
    if not draft:
        raise HTTPException(
            503, "AI drafting is unavailable right now — write the topic manually"
        )
    return {"draft": draft}


# ---------------------------------------------------------------------------
# Public blog + sitemap + robots
# ---------------------------------------------------------------------------

@public_router.get("/blog")
async def public_blog_list(db: AsyncSession = Depends(get_db)):
    """Published posts across all shops, latest first (public marketing)."""
    result = await db.execute(
        select(BlogPost, Tenant.page_name, Tenant.website_url)
        .join(Tenant, BlogPost.tenant_id == Tenant.id)
        .where(BlogPost.status == "published")
        .order_by(BlogPost.published_at.desc())
        .limit(50)
    )
    rows = result.all()
    return {
        "posts": [
            {
                "slug": post.slug,
                "title": post.title,
                "shop": shop_name,
                "cover_image_url": post.cover_image_url,
                "meta_description": post.meta_description,
                "published_at": post.published_at.isoformat() if post.published_at else None,
            }
            for post, shop_name, _site in rows
        ]
    }


@public_router.get("/blog/{slug}")
async def public_blog_post(slug: str, db: AsyncSession = Depends(get_db)):
    """Rendered post — every text node HTML-escaped (XSS-safe by design)."""
    result = await db.execute(
        select(BlogPost, Tenant.page_name, Tenant.website_url)
        .join(Tenant, BlogPost.tenant_id == Tenant.id)
        .where(BlogPost.slug == slug, BlogPost.status == "published")
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Post not found")
    post, shop_name, website_url = row
    html = blog_service.render_blocks_to_html(post.blocks, website_url)
    return {
        "slug": post.slug,
        "title": post.title,
        "shop": shop_name,
        "meta_description": post.meta_description,
        "cover_image_url": post.cover_image_url,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "html": html,
    }


@public_router.get("/sitemap.xml")
async def sitemap(request: Request, db: AsyncSession = Depends(get_db)):
    """SEO: every published post + shop homepage, escaped URLs."""
    result = await db.execute(
        select(BlogPost, Tenant)
        .join(Tenant, BlogPost.tenant_id == Tenant.id)
        .where(BlogPost.status == "published")
        .order_by(BlogPost.published_at.desc())
        .limit(1000)
    )
    rows = result.all()

    base = get_settings().PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    today = __import__("datetime").date.today().isoformat()

    urls = [f"  <url><loc>{_xml_escape(base)}/</loc><lastmod>{today}</lastmod><priority>1.0</priority></url>"]
    for post, tenant in rows:
        loc = f"{base}/blog/{quote(post.slug)}"
        lastmod = post.published_at.date().isoformat() if post.published_at else today
        urls.append(
            f"  <url><loc>{_xml_escape(loc)}</loc>"
            f"<lastmod>{lastmod}</lastmod><priority>0.7</priority></url>"
        )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n</urlset>"
    )
    return Response(content=body, media_type="application/xml")


@public_router.get("/robots.txt")
async def robots():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /blog\n"
        "Disallow: /api\n"
        "Disallow: /dashboard\n"
        f"Sitemap: {get_settings().PUBLIC_BASE_URL or ''}/sitemap.xml\n"
    )
    return Response(content=body, media_type="text/plain")


def _xml_escape(value: str) -> str:
    from xml.sax.saxutils import escape
    return escape(value)
