"""API endpoints for social media scheduling and insights.

Endpoints:
- POST /api/tenants/{id}/schedule/post — schedule a new post
- GET /api/tenants/{id}/schedule/posts — list scheduled posts
- DELETE /api/tenants/{id}/schedule/posts/{post_id} — cancel scheduled post
- POST /api/tenants/{id}/schedule/generate-caption — AI caption generation
- GET /api/tenants/{id}/insights/overview — FB+IG insights overview
- GET /api/tenants/{id}/insights/best-time — best time to post (IG online_followers heatmap)
- GET /api/tenants/{id}/insights/post/{post_id} — per-post insights
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timezone

from app.database import get_db
from app.dependencies import get_tenant
from app.models.tenant import Tenant
from app.models.scheduled_post import ScheduledPost, PostInsights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}", tags=["Scheduling & Insights"])


# ============================================================
# Pydantic schemas
# ============================================================

class SchedulePostRequest(BaseModel):
    platform: str = Field(..., description="facebook or instagram")
    caption: str = Field(..., min_length=1, max_length=5000)
    media_urls: list[str] = Field(default_factory=list)
    media_type: str = Field("text", description="text, photo, video, reel, story, carousel")
    link: Optional[str] = None
    scheduled_at: datetime
    ai_generated: bool = False


class GenerateCaptionRequest(BaseModel):
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    platform: str = "facebook"
    tone: str = "friendly"
    include_hashtags: bool = True
    language: str = "arabic"  # arabic, english, mixed


class UpdatePostStatusRequest(BaseModel):
    status: str  # draft, scheduled, cancelled


# ============================================================
# Post scheduling endpoints
# ============================================================

@router.post("/schedule/post", status_code=201)
async def schedule_post(
    req: SchedulePostRequest,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Schedule a new social media post.

    The post will be published at `scheduled_at` by a background worker.
    """
    if req.platform not in ("facebook", "instagram"):
        raise HTTPException(status_code=422, detail="Platform must be 'facebook' or 'instagram'")

    # Normalize to naive UTC — clients send ISO strings with 'Z' (offset-aware),
    # the DB stores naive UTC. Accept both forms.
    scheduled_at = req.scheduled_at
    if scheduled_at.tzinfo is not None:
        scheduled_at = scheduled_at.astimezone(timezone.utc).replace(tzinfo=None)

    if scheduled_at <= datetime.utcnow():
        raise HTTPException(status_code=422, detail="scheduled_at must be in the future")

    # Validate media requirements
    if req.media_type in ("photo", "video", "reel", "story", "carousel") and not req.media_urls:
        raise HTTPException(
            status_code=422,
            detail=f"media_urls required for media_type '{req.media_type}'",
        )

    post = ScheduledPost(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        platform=req.platform,
        caption=req.caption,
        media_urls=req.media_urls,
        media_type=req.media_type,
        link=req.link,
        scheduled_at=scheduled_at,
        status="scheduled",
        ai_generated=req.ai_generated,
    )
    db.add(post)
    await db.commit()

    return {
        "id": str(post.id),
        "status": "scheduled",
        "scheduled_at": post.scheduled_at.isoformat(),
        "platform": post.platform,
    }


@router.get("/schedule/posts")
async def list_scheduled_posts(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List scheduled posts for this tenant."""
    query = (
        select(ScheduledPost)
        .where(ScheduledPost.tenant_id == tenant.id)
        .order_by(ScheduledPost.scheduled_at.desc())
        .limit(limit)
    )
    if status:
        query = query.where(ScheduledPost.status == status)
    if platform:
        query = query.where(ScheduledPost.platform == platform)

    result = await db.execute(query)
    posts = result.scalars().all()

    return {
        "posts": [
            {
                "id": str(p.id),
                "platform": p.platform,
                "caption": p.caption[:200] + "..." if len(p.caption) > 200 else p.caption,
                "media_type": p.media_type,
                "media_urls": p.media_urls,
                "scheduled_at": p.scheduled_at.isoformat(),
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "status": p.status,
                "platform_post_id": p.platform_post_id,
                "error_message": p.error_message,
                "ai_generated": p.ai_generated,
            }
            for p in posts
        ],
        "total": len(posts),
    }


@router.patch("/schedule/posts/{post_id}/status")
async def update_post_status(
    post_id: uuid.UUID,
    req: UpdatePostStatusRequest,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update a scheduled post's status (e.g., cancel it)."""
    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.tenant_id == tenant.id,
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.status in ("published", "publishing"):
        raise HTTPException(status_code=400, detail="Cannot modify a published post")

    if req.status not in ("draft", "scheduled", "cancelled"):
        raise HTTPException(status_code=422, detail="Invalid status")

    post.status = req.status
    await db.commit()

    return {"status": "updated", "post_id": str(post.id), "new_status": post.status}


@router.delete("/schedule/posts/{post_id}")
async def delete_scheduled_post(
    post_id: uuid.UUID,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduled post (only if not yet published)."""
    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.tenant_id == tenant.id,
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.status == "published":
        raise HTTPException(status_code=400, detail="Cannot delete a published post")

    await db.delete(post)
    await db.commit()

    return {"status": "deleted", "post_id": str(post_id)}


# ============================================================
# AI caption generation
# ============================================================

@router.post("/schedule/generate-caption")
async def generate_caption(
    req: GenerateCaptionRequest,
    tenant: Tenant = Depends(get_tenant),
):
    """Generate AI-powered captions for social media posts.

    Uses the tenant's style profile (if available) to match their voice.
    Returns 3 caption variants + hashtag suggestions.
    """
    try:
        from app.ai.llm_client import chat_completion_with_usage
    except ImportError:
        raise HTTPException(status_code=500, detail="LLM client not available")

    # Build the prompt
    style_hint = ""
    if tenant.style_profile:
        profile = tenant.style_profile
        style_hint = f"""
Match this merchant's communication style:
- Tone: {profile.get('tone', 'friendly')}
- Greeting patterns: {', '.join(profile.get('greeting_patterns', [])[:3])}
- Signoff patterns: {', '.join(profile.get('signoff_patterns', [])[:3])}
- Emoji frequency: {profile.get('emoji_frequency', 'low')}
- Language mix: {profile.get('language_mix', {})}
"""

    language_instruction = {
        "arabic": "Write in Egyptian Arabic (عامية مصرية).",
        "english": "Write in natural English.",
        "mixed": "Write in Egyptian Arabic with some English mixed in (code-switching).",
    }.get(req.language, "Write in Egyptian Arabic.")

    platform_hint = {
        "facebook": "For Facebook Page (max 5000 chars, 1-2 hashtags, conversational tone).",
        "instagram": "For Instagram feed (max 2200 chars, front-load hook in first 125 chars, 5-10 hashtags at end).",
    }.get(req.platform, "")

    prompt = f"""You are a social media content creator for an Egyptian small business.

Create 3 caption variants for a post about:
- Product: {req.product_name or 'general business update'}
- Description: {req.product_description or 'N/A'}
- Platform: {req.platform}
- Tone: {req.tone}
- Language: {language_instruction}
{platform_hint}
{style_hint}

Return JSON ONLY with this format:
{{
  "captions": [
    "caption 1...",
    "caption 2...",
    "caption 3..."
  ],
  "hashtags": ["#hashtag1", "#hashtag2", ...]
}}

If include_hashtags is false, return empty hashtags array.
Be creative and engaging. Use emojis naturally if the merchant's style uses them."""

    try:
        result = await chat_completion_with_usage([
            {"role": "system", "content": "You are a social media content creator. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ])

        import json
        import re
        json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            return {
                "captions": data.get("captions", []),
                "hashtags": data.get("hashtags", []) if req.include_hashtags else [],
                "tokens_used": result.total_tokens,
            }
        else:
            return {
                "captions": [result.content],
                "hashtags": [],
                "tokens_used": result.total_tokens,
            }
    except Exception as e:
        logger.error(f"Caption generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Caption generation failed: {e}")


# ============================================================
# Insights endpoints
# ============================================================

@router.get("/insights/overview")
async def get_insights_overview(
    tenant: Tenant = Depends(get_tenant),
    days: int = Query(30, ge=1, le=90),
):
    """Get FB + IG insights overview for the tenant.

    Returns reach, impressions, engagement for both platforms.
    """
    from datetime import timedelta
    from app.scheduling.facebook_publisher import get_page_insights, get_page_info
    from app.scheduling.instagram_publisher import get_ig_user_insights

    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    until = datetime.utcnow().strftime("%Y-%m-%d")

    overview = {
        "facebook": None,
        "instagram": None,
        "period_days": days,
    }

    # Facebook insights
    if tenant.fb_page_id and tenant.page_access_token:
        try:
            fb_insights = await get_page_insights(
                tenant.page_access_token,
                tenant.fb_page_id,
                since=since,
                until=until,
            )
            fb_info = await get_page_info(tenant.page_access_token, tenant.fb_page_id)
            overview["facebook"] = {
                "page_name": fb_info.get("name"),
                "followers": fb_info.get("followers_count", 0),
                "fans": fb_info.get("fan_count", 0),
                "insights": fb_insights.get("data", []),
            }
        except Exception as e:
            overview["facebook"] = {"error": str(e)}

    # Instagram insights
    if tenant.ig_user_id and tenant.ig_access_token:
        try:
            ig_insights = await get_ig_user_insights(
                tenant.ig_access_token,
                tenant.ig_user_id,
                since=since,
                until=until,
            )
            overview["instagram"] = {
                "insights": ig_insights.get("data", []),
            }
        except Exception as e:
            overview["instagram"] = {"error": str(e)}

    return overview


@router.get("/insights/best-time")
async def get_best_time_to_post(
    tenant: Tenant = Depends(get_tenant),
):
    """Get the best time to post on Instagram (based on online_followers heatmap).

    Returns a 7×24 heatmap + top 5 recommended posting slots.
    """
    if not tenant.ig_user_id or not tenant.ig_access_token:
        raise HTTPException(
            status_code=400,
            detail="Instagram account not connected. Connect IG to get best-time insights.",
        )

    from app.scheduling.instagram_publisher import get_best_time_to_post as _get_best_time

    try:
        result = await _get_best_time(tenant.ig_access_token, tenant.ig_user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch best-time data: {e}")


@router.get("/insights/post/{post_id}")
async def get_post_insights(
    post_id: uuid.UUID,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get insights for a specific published post."""
    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.tenant_id == tenant.id,
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.status != "published" or not post.platform_post_id:
        raise HTTPException(status_code=400, detail="Post not yet published")

    # Check cache first
    cache_result = await db.execute(
        select(PostInsights).where(
            PostInsights.scheduled_post_id == post.id
        ).order_by(PostInsights.fetched_at.desc()).limit(1)
    )
    cached = cache_result.scalar_one_or_none()
    if cached and (datetime.utcnow() - cached.fetched_at).total_seconds() < 3600:  # 1 hour cache
        return {"post_id": str(post.id), "metrics": cached.metrics, "cached": True}

    # Fetch fresh insights
    try:
        if post.platform == "facebook":
            from app.scheduling.facebook_publisher import get_page_post_insights
            data = await get_page_post_insights(tenant.page_access_token, post.platform_post_id)
        else:  # instagram
            from app.scheduling.instagram_publisher import get_ig_media_insights
            data = await get_ig_media_insights(tenant.ig_access_token, post.platform_post_id)

        # Cache the result
        insights = PostInsights(
            id=uuid.uuid4(),
            scheduled_post_id=post.id,
            platform=post.platform,
            platform_post_id=post.platform_post_id,
            metrics=data.get("data", []),
        )
        db.add(insights)
        await db.commit()

        return {"post_id": str(post.id), "metrics": data.get("data", []), "cached": False}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch insights: {e}")
