"""API endpoints that bridge Zemest to the Postiz sidecar.

These endpoints let our dashboard talk to Postiz through our API,
so the frontend only needs to know about one backend (us).

Endpoints:
- GET  /api/tenants/{id}/postiz/health — check if Postiz is running
- POST /api/tenants/{id}/postiz/login — login to Postiz
- GET  /api/tenants/{id}/postiz/integrations — list connected social accounts
- POST /api/tenants/{id}/postiz/connect/{provider} — get OAuth URL for a provider
- POST /api/tenants/{id}/postiz/posts — create/schedule a post via Postiz
- GET  /api/tenants/{id}/postiz/posts — list posts from Postiz
- GET  /api/tenants/{id}/postiz/posts/{id}/stats — get post statistics
- DELETE /api/tenants/{id}/postiz/posts/{group_id} — delete a post
- GET  /api/tenants/{id}/postiz/best-time — find next free posting slot
- POST /api/tenants/{id}/postiz/generate — AI caption generation via Postiz
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant
from app.models.tenant import Tenant
from app.scheduling.postiz_client import get_postiz_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}/postiz", tags=["Postiz Scheduler"])


# ============================================================
# Pydantic schemas
# ============================================================

class PostizLoginRequest(BaseModel):
    email: str
    password: str


class PostizCreatePostRequest(BaseModel):
    integration_id: str = Field(..., description="Postiz integration ID (from list_integrations)")
    caption: str = Field(..., min_length=1, max_length=5000)
    media_urls: list[str] = Field(default_factory=list)
    schedule_at: Optional[str] = Field(None, description="ISO datetime. If None, saves as draft.")


class PostizGenerateRequest(BaseModel):
    prompt: str = Field(..., description="What to write about")
    number_of_posts: int = Field(3, ge=1, le=10)
    platforms: list[str] = Field(default_factory=list)


# ============================================================
# Health & Auth
# ============================================================

@router.get("/health")
async def postiz_health():
    """Check if the Postiz sidecar is running and reachable."""
    client = get_postiz_client()
    healthy = await client.health_check()
    return {"healthy": healthy, "url": client.base_url}


@router.post("/login")
async def postiz_login(
    req: PostizLoginRequest,
    tenant: Tenant = Depends(get_tenant),
):
    """Login to Postiz. The JWT is stored in the PostizClient singleton."""
    client = get_postiz_client()
    success = await client.login(req.email, req.password)
    if not success:
        raise HTTPException(status_code=401, detail="Postiz login failed")
    return {"status": "logged_in"}


@router.get("/can-register")
async def postiz_can_register():
    """Check if Postiz allows new registrations."""
    client = get_postiz_client()
    can = await client.check_can_register()
    return {"can_register": can}


# ============================================================
# Integrations (connected social accounts)
# ============================================================

@router.get("/integrations")
async def list_postiz_integrations(
    tenant: Tenant = Depends(get_tenant),
):
    """List all social accounts connected to Postiz (FB Pages, IG accounts, etc.)."""
    client = get_postiz_client()
    integrations = await client.list_integrations()
    return {"integrations": integrations}


@router.post("/connect/{provider}")
async def get_connect_url(
    provider: str,
    tenant: Tenant = Depends(get_tenant),
):
    """Get the OAuth URL to connect a social account to Postiz.

    Supported providers: facebook, instagram, instagram_standalone, x, linkedin, etc.
    """
    client = get_postiz_client()
    url = await client.get_connect_url(provider)
    if not url:
        raise HTTPException(status_code=400, detail=f"Failed to get OAuth URL for {provider}")
    return {"url": url, "provider": provider}


# ============================================================
# Posts
# ============================================================

@router.post("/posts")
async def create_postiz_post(
    req: PostizCreatePostRequest,
    tenant: Tenant = Depends(get_tenant),
):
    """Create/schedule a post via Postiz.

    Postiz handles the actual Graph API call to FB/IG.
    """
    client = get_postiz_client()

    # Build the Postiz post payload
    posts_payload = [{
        "integrationId": req.integration_id,
        "content": req.caption,
        "mediaUrls": req.media_urls,
        "settings": {},  # platform-specific settings (can be extended)
    }]

    result = await client.create_post(
        posts=posts_payload,
        schedule_at=req.schedule_at,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Postiz failed to create post")

    return {"status": "created", "postiz_result": result}


@router.get("/posts")
async def list_postiz_posts(
    tenant: Tenant = Depends(get_tenant),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    filter_type: str = Query("scheduled"),
):
    """List posts from Postiz.

    filter_type: 'scheduled', 'published', 'draft', 'failed'
    """
    client = get_postiz_client()
    result = await client.list_posts(page=page, limit=limit, filter_type=filter_type)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to fetch posts from Postiz")

    return result


@router.get("/posts/{post_id}/stats")
async def get_postiz_post_stats(
    post_id: str,
    tenant: Tenant = Depends(get_tenant),
):
    """Get statistics/insights for a specific post via Postiz."""
    client = get_postiz_client()
    stats = await client.get_post_statistics(post_id)

    if stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch stats from Postiz")

    return stats


@router.delete("/posts/{group_id}")
async def delete_postiz_post(
    group_id: str,
    tenant: Tenant = Depends(get_tenant),
):
    """Delete a post from Postiz (by group ID)."""
    client = get_postiz_client()
    success = await client.delete_post(group_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete post in Postiz")

    return {"status": "deleted", "group_id": group_id}


@router.put("/posts/{post_id}/reschedule")
async def reschedule_postiz_post(
    post_id: str,
    new_date: str = Query(..., description="ISO datetime string"),
    tenant: Tenant = Depends(get_tenant),
):
    """Reschedule a post to a new time."""
    client = get_postiz_client()
    success = await client.update_post_date(post_id, new_date, action="update")

    if not success:
        raise HTTPException(status_code=500, detail="Failed to reschedule post in Postiz")

    return {"status": "rescheduled", "post_id": post_id, "new_date": new_date}


@router.get("/best-time")
async def find_postiz_free_slot(
    tenant: Tenant = Depends(get_tenant),
    integration_id: Optional[str] = Query(None),
):
    """Find the next free time slot for posting via Postiz."""
    client = get_postiz_client()
    slot = await client.find_free_slot(integration_id)

    if not slot:
        raise HTTPException(status_code=500, detail="Failed to find free slot in Postiz")

    return {"next_free_slot": slot}


# ============================================================
# AI Caption Generation
# ============================================================

@router.post("/generate")
async def generate_postiz_posts(
    req: PostizGenerateRequest,
    tenant: Tenant = Depends(get_tenant),
):
    """Use Postiz's built-in AI to generate post ideas.

    Postiz streams results — this endpoint collects them all and returns
    as a list. Falls back to our own LLM if Postiz is unavailable.
    """
    client = get_postiz_client()
    results = await client.generate_posts(
        prompt=req.prompt,
        number_of_posts=req.number_of_posts,
        platforms=req.platforms,
    )

    if not results:
        # Fallback to our own LLM
        try:
            from app.ai.llm_client import chat_completion_with_usage
            import json
            import re

            style_hint = ""
            if tenant.style_profile:
                p = tenant.style_profile
                style_hint = f"Tone: {p.get('tone', 'friendly')}. Emoji: {p.get('emoji_frequency', 'low')}."

            llm_result = await chat_completion_with_usage([
                {"role": "system", "content": "You are a social media content creator. Return valid JSON only."},
                {"role": "user", "content": f"""Generate {req.number_of_posts} social media post captions about: {req.prompt}
                {style_hint}
                Return JSON: {{"posts": ["caption1", "caption2", ...]}}"""},
            ])

            json_match = re.search(r'\{.*\}', llm_result.content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return {"posts": data.get("posts", []), "source": "zemest_fallback"}
        except Exception as e:
            logger.error(f"Fallback caption generation failed: {e}")

        raise HTTPException(status_code=500, detail="Postiz AI generation failed and fallback also failed")

    return {"posts": results, "source": "postiz"}
