"""Instagram Graph API client for publishing and insights.

Instagram uses a two-step container pattern:
1. Create media container: POST /{ig-user-id}/media
2. Publish container: POST /{ig-user-id}/media_publish

The IG account must be a Business or Creator account.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

IG_GRAPH_URL = settings.FB_GRAPH_API_URL  # Same base URL as FB


async def create_media_container(
    access_token: str,
    ig_user_id: str,
    media_type: str,  # IMAGE, VIDEO, REELS, STORIES, CAROUSEL
    media_url: str,
    caption: str = "",
    **kwargs,
) -> str:
    """Step 1: Create an IG media container.

    Args:
        media_type: IMAGE, VIDEO, REELS, STORIES, or CAROUSEL
        media_url: Publicly accessible URL of the media
        caption: Post caption (max 2200 chars for feed posts)

    Returns: container_id (use with publish_media_container)
    """
    url = f"{IG_GRAPH_URL}/{ig_user_id}/media"
    payload = {
        "media_type": media_type,
        "image_url" if media_type == "IMAGE" else "video_url": media_url,
        "caption": caption,
        "access_token": access_token,
    }

    # Add REELS-specific fields
    if media_type == "REELS":
        if "share_to_feed" in kwargs:
            payload["share_to_feed"] = str(kwargs["share_to_feed"]).lower()
        if "audio_name" in kwargs:
            payload["audio_name"] = kwargs["audio_name"]
        if "cover_url" in kwargs:
            payload["cover_url"] = kwargs["cover_url"]

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, data=payload)
        data = resp.json()

    if "error" in data:
        logger.error(f"IG create container error: {data['error']}")
        raise Exception(f"IG API error: {data['error'].get('message', 'Unknown')}")

    return data.get("id")


async def check_container_status(
    access_token: str,
    container_id: str,
) -> str:
    """Check the processing status of a media container.

    Returns: 'IN_PROGRESS', 'FINISHED', or 'ERROR'
    """
    url = f"{IG_GRAPH_URL}/{container_id}"
    params = {
        "fields": "status_code",
        "access_token": access_token,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "error" in data:
        logger.error(f"IG container status error: {data['error']}")
        return "ERROR"

    return data.get("status_code", "IN_PROGRESS")


async def publish_media_container(
    access_token: str,
    ig_user_id: str,
    creation_id: str,
) -> dict:
    """Step 2: Publish a finished media container."""
    url = f"{IG_GRAPH_URL}/{ig_user_id}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": access_token,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, data=payload)
        data = resp.json()

    if "error" in data:
        logger.error(f"IG publish error: {data['error']}")
        raise Exception(f"IG API error: {data['error'].get('message', 'Unknown')}")

    return data


async def publish_image(
    access_token: str,
    ig_user_id: str,
    image_url: str,
    caption: str = "",
) -> dict:
    """Publish a single image to Instagram feed.

    Two-step: create container → publish.
    """
    container_id = await create_media_container(
        access_token, ig_user_id, "IMAGE", image_url, caption
    )
    return await publish_media_container(access_token, ig_user_id, container_id)


async def publish_reel(
    access_token: str,
    ig_user_id: str,
    video_url: str,
    caption: str = "",
    share_to_feed: bool = True,
    cover_url: Optional[str] = None,
) -> dict:
    """Publish a Reel to Instagram.

    Two-step with status polling (videos take time to process).
    """
    container_id = await create_media_container(
        access_token, ig_user_id, "REELS", video_url, caption,
        share_to_feed=share_to_feed, cover_url=cover_url,
    )

    # Poll until processing is done
    max_retries = 30
    for _ in range(max_retries):
        status = await check_container_status(access_token, container_id)
        if status == "FINISHED":
            break
        elif status == "ERROR":
            raise Exception("IG video processing failed")
        await asyncio.sleep(5)  # wait 5s between checks

    return await publish_media_container(access_token, ig_user_id, container_id)


async def publish_story(
    access_token: str,
    ig_user_id: str,
    media_url: str,
    media_type: str = "IMAGE",  # IMAGE or VIDEO
) -> dict:
    """Publish a Story to Instagram."""
    container_id = await create_media_container(
        access_token, ig_user_id, "STORIES", media_url, ""
    )
    return await publish_media_container(access_token, ig_user_id, container_id)


# ============================================================
# Instagram Insights
# ============================================================

async def get_ig_user_insights(
    access_token: str,
    ig_user_id: str,
    metric: str = "impressions,reach,profile_views,follower_count",
    period: str = "day",
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> dict:
    """Fetch Instagram account-level insights.

    Available metrics:
    - impressions: total times content was seen
    - reach: number of unique accounts that saw content
    - profile_views: profile view count
    - follower_count: total followers
    - email_contacts, phone_call_clicks, text_message_clicks, get_directions_clicks
    - website_clicks

    Data is kept for 90 days. Up to 48h delay.
    """
    url = f"{IG_GRAPH_URL}/{ig_user_id}/insights"
    params = {
        "metric": metric,
        "period": period,
        "access_token": access_token,
    }
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "error" in data:
        logger.error(f"IG insights error: {data['error']}")
        raise Exception(f"IG API error: {data['error'].get('message', 'Unknown')}")

    return data


async def get_online_followers(
    access_token: str,
    ig_user_id: str,
) -> dict:
    """Fetch the online_followers metric (last 30 days).

    Returns a 7×24 heatmap of when followers are online —
    this is the KEY metric for "best time to post" calculation.
    """
    url = f"{IG_GRAPH_URL}/{ig_user_id}/insights"
    params = {
        "metric": "online_followers",
        "period": "total",
        "access_token": access_token,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "error" in data:
        logger.error(f"IG online_followers error: {data['error']}")
        raise Exception(f"IG API error: {data['error'].get('message', 'Unknown')}")

    return data


async def get_ig_media_insights(
    access_token: str,
    media_id: str,
) -> dict:
    """Fetch insights for a specific IG media post.

    Returns: impressions, reach, engagement, saved, likes, comments, shares, video_views.
    """
    url = f"{IG_GRAPH_URL}/{media_id}/insights"
    params = {
        "metric": "impressions,reach,engagement,saved,likes,comments,shares",
        "access_token": access_token,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "error" in data:
        logger.error(f"IG media insights error: {data['error']}")
        raise Exception(f"IG API error: {data['error'].get('message', 'Unknown')}")

    return data


async def get_best_time_to_post(
    access_token: str,
    ig_user_id: str,
) -> dict:
    """Calculate the best time to post based on online_followers heatmap.

    Returns: {
        "heatmap": [[day, hour, value], ...],  # 7×24 grid
        "top_slots": [{"day": "Monday", "hour": 20, "score": 95}, ...]  # top 5
    }
    """
    data = await get_online_followers(access_token, ig_user_id)

    # Parse the online_followers data
    # Format: {"data": [{"name": "online_followers", "total_value": {"value": [{"day": [0-6], "hour": [0-23], "value": N}, ...]}}]}
    try:
        values = data["data"][0]["total_value"]["value"]
    except (KeyError, IndexError):
        return {"heatmap": [], "top_slots": []}

    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    # Build heatmap
    heatmap = []
    for entry in values:
        day_idx = entry.get("day", 0)
        hour = entry.get("hour", 0)
        value = entry.get("value", 0)
        heatmap.append({
            "day": days[day_idx] if 0 <= day_idx < 7 else "Unknown",
            "day_index": day_idx,
            "hour": hour,
            "value": value,
        })

    # Sort by value to find top slots
    sorted_slots = sorted(heatmap, key=lambda x: -x["value"])
    top_slots = [
        {
            "day": slot["day"],
            "hour": slot["hour"],
            "formatted_time": _format_hour(slot["hour"]),
            "score": min(100, int(slot["value"] / max(1, sorted_slots[0]["value"]) * 100)),
        }
        for slot in sorted_slots[:5]
    ]

    return {"heatmap": heatmap, "top_slots": top_slots}


def _format_hour(hour: int) -> str:
    """Format hour as 12-hour time string."""
    if hour == 0:
        return "12 AM"
    elif hour < 12:
        return f"{hour} AM"
    elif hour == 12:
        return "12 PM"
    else:
        return f"{hour - 12} PM"
