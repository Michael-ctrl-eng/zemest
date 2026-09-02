"""Facebook Graph API client for Page publishing and insights.

Uses direct httpx calls (no heavy SDK needed) — following Postiz's approach.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

FB_GRAPH_URL = settings.FB_GRAPH_API_URL  # re-versioned to v22.0 by graph_client at call time


# ============================================================
# Page publishing
# ============================================================

async def publish_feed_post(
    page_access_token: str,
    page_id: str,
    message: str,
    link: Optional[str] = None,
    scheduled_publish_time: Optional[int] = None,
) -> dict:
    """Publish a text/link post to a Facebook Page.

    Args:
        page_access_token: Page access token (long-lived)
        page_id: Facebook Page ID
        message: Post text/caption
        link: Optional URL to attach
        scheduled_publish_time: Optional Unix timestamp (seconds) to schedule.
            If provided, post is created as unpublished and published at that time.

    Returns: {"id": "post_id"} on success.
    """
    url = f"{FB_GRAPH_URL}/{page_id}/feed"
    payload = {
        "message": message,
    }
    if link:
        payload["link"] = link
    if scheduled_publish_time:
        payload["published"] = "false"
        payload["scheduled_publish_time"] = str(scheduled_publish_time)

    async with httpx.AsyncClient(timeout=30) as client:
        # Bearer header — token never in the request body/URL (audit G5).
        resp = await client.post(
            url, data=payload,
            headers={"Authorization": f"Bearer {page_access_token}"},
        )
        data = resp.json()

    if "error" in data:
        logger.error(f"FB publish error: {data['error']}")
        raise Exception(f"FB API error: {data['error'].get('message', 'Unknown')}")

    return data


async def publish_photo(
    page_access_token: str,
    page_id: str,
    photo_url: str,
    caption: str = "",
    scheduled_publish_time: Optional[int] = None,
) -> dict:
    """Publish a photo to a Facebook Page.

    Args:
        photo_url: Publicly accessible URL of the photo (FB must be able to fetch it).
        caption: Photo caption.
    """
    url = f"{FB_GRAPH_URL}/{page_id}/photos"
    payload = {
        "url": photo_url,
        "message": caption,
    }
    if scheduled_publish_time:
        payload["published"] = "false"
        payload["scheduled_publish_time"] = str(scheduled_publish_time)

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url, data=payload,
            headers={"Authorization": f"Bearer {page_access_token}"},
        )
        data = resp.json()

    if "error" in data:
        logger.error(f"FB photo publish error: {data['error']}")
        raise Exception(f"FB API error: {data['error'].get('message', 'Unknown')}")

    return data


async def publish_video(
    page_access_token: str,
    page_id: str,
    video_url: str,
    title: str = "",
    description: str = "",
) -> dict:
    """Publish a video/reel to a Facebook Page.

    Args:
        video_url: Publicly accessible URL of the video file.
    """
    url = f"{FB_GRAPH_URL}/{page_id}/videos"
    payload = {
        "file_url": video_url,
        "title": title,
        "description": description,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            url, data=payload,
            headers={"Authorization": f"Bearer {page_access_token}"},
        )
        data = resp.json()

    if "error" in data:
        logger.error(f"FB video publish error: {data['error']}")
        raise Exception(f"FB API error: {data['error'].get('message', 'Unknown')}")

    return data


# ============================================================
# Page insights
# ============================================================

async def get_page_insights(
    page_access_token: str,
    page_id: str,
    metric: str = "page_impressions,page_reach,page_engaged_users,page_fans",
    period: str = "day",
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> dict:
    """Fetch Facebook Page insights.

    Common metrics:
    - page_impressions: number of times Page content was on screen
    - page_reach: number of people who saw Page content
    - page_engaged_users: number of people who engaged with Page
    - page_fans: total Page likes
    - page_post_engagements: total engagements on posts

    Note: Page must have 100+ likes to access insights.
    """
    url = f"{FB_GRAPH_URL}/{page_id}/insights"
    params = {
        "metric": metric,
        "period": period,
    }
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url, params=params,
            headers={"Authorization": f"Bearer {page_access_token}"},
        )
        data = resp.json()

    if "error" in data:
        logger.error(f"FB insights error: {data['error']}")
        raise Exception(f"FB API error: {data['error'].get('message', 'Unknown')}")

    return data


async def get_page_post_insights(
    page_access_token: str,
    post_id: str,
) -> dict:
    """Fetch insights for a specific Page post.

    Returns metrics: post_impressions, post_reach, post_engaged_users,
    post_reactions_like_total, post_comments, post_shares.
    """
    url = f"{FB_GRAPH_URL}/{post_id}/insights"
    params = {
        "metric": "post_impressions,post_reach,post_engaged_users,post_reactions_like_total",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url, params=params,
            headers={"Authorization": f"Bearer {page_access_token}"},
        )
        data = resp.json()

    if "error" in data:
        logger.error(f"FB post insights error: {data['error']}")
        raise Exception(f"FB API error: {data['error'].get('message', 'Unknown')}")

    return data


async def get_page_info(
    page_access_token: str,
    page_id: str,
) -> dict:
    """Fetch basic Page info (name, followers, fan_count)."""
    url = f"{FB_GRAPH_URL}/{page_id}"
    params = {
        "fields": "name,followers_count,fan_count,about,website,phone",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url, params=params,
            headers={"Authorization": f"Bearer {page_access_token}"},
        )
        data = resp.json()

    if "error" in data:
        logger.error(f"FB page info error: {data['error']}")
        raise Exception(f"FB API error: {data['error'].get('message', 'Unknown')}")

    return data
