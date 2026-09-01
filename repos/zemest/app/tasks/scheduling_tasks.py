"""Huey task to publish scheduled posts at their scheduled time.

APScheduler triggers this every 30s (app/main.py lifespan — previously
Celery beat every minute + the 30s inline worker loop); it finds posts due
for publishing, publishes them via FB/IG Graph API, and updates status.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.tasks.huey_app import huey_app
from app.database import async_session
from app.models.scheduled_post import ScheduledPost
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Bounded publish retries: stuck/failed posts retry at most 3 times, then
# stay failed with a real error message (no infinite hot-loop).
MAX_PUBLISH_RETRIES = 3


@huey_app.task(name="publish_scheduled_posts")
def publish_scheduled_posts():
    """Find and publish all posts scheduled for now or earlier.

    Scheduled by APScheduler every 30s (see app/main.py lifespan).
    """
    return _run_async(_publish_due_posts_async())


async def _publish_due_posts_async():
    """Async implementation of scheduled post publishing."""
    async with async_session() as db:
        now = datetime.utcnow()

        # --- Crash-safety: recover posts stuck in 'publishing' -------------
        # A daemon restart mid-publish leaves rows in 'publishing' forever.
        # Anything stuck > 5 minutes is dead: bounded retry via retry_count
        # (≤ 3 attempts), then a terminal 'failed'.
        try:
            stuck_cutoff = now - timedelta(minutes=5)
            stuck = await db.execute(
                select(ScheduledPost).where(
                    ScheduledPost.status == "publishing",
                    ScheduledPost.updated_at <= stuck_cutoff,
                )
            )
            stuck_posts = list(stuck.scalars().all())
            for post in stuck_posts:
                post.retry_count = (post.retry_count or 0) + 1
                if post.retry_count >= MAX_PUBLISH_RETRIES:
                    post.status = "failed"
                    post.error_message = "Timed out while publishing (worker restart) — gave up after max retries"
                    logger.error(f"Post {post.id} stuck in publishing; marked failed after {post.retry_count} attempts")
                else:
                    post.status = "scheduled"
                    post.error_message = "Recovered after stuck publish — retrying"
                    logger.warning(f"Post {post.id} recovered from stuck 'publishing'; retry #{post.retry_count}")
            if stuck_posts:
                await db.commit()
        except Exception:
            logger.exception("Stuck-publish recovery failed (continuing)")

        # --- Bounded retry of failed posts ----------------------------------
        # Genuine failures (expired token, deleted media) retry up to
        # MAX_PUBLISH_RETRIES with a 5-minute backoff between attempts.
        try:
            retry_cutoff = now - timedelta(minutes=5)
            retryable = await db.execute(
                select(ScheduledPost).where(
                    ScheduledPost.status == "failed",
                    ScheduledPost.retry_count < MAX_PUBLISH_RETRIES,
                    ScheduledPost.updated_at <= retry_cutoff,
                )
            )
            for post in list(retryable.scalars().all()):
                post.status = "scheduled"
                logger.info(f"Post {post.id} requeued for retry (attempt {post.retry_count + 1}/{MAX_PUBLISH_RETRIES})")
            await db.commit()
        except Exception:
            logger.exception("Failed-post requeue failed (continuing)")

        # Find posts due for publishing
        result = await db.execute(
            select(ScheduledPost).where(
                ScheduledPost.status == "scheduled",
                ScheduledPost.scheduled_at <= now,
            ).limit(50)  # process in batches
        )
        due_posts = result.scalars().all()

        if not due_posts:
            return {"published": 0, "failed": 0, "total": 0}

        published_count = 0
        failed_count = 0

        for post in due_posts:
            # Mark as publishing
            post.status = "publishing"
            await db.commit()

            try:
                # Fetch the tenant for credentials
                tenant = await db.get(Tenant, post.tenant_id)
                if not tenant:
                    raise Exception("Tenant not found")

                # Publish based on platform
                platform_post_id = await _publish_post(post, tenant)

                # Mark as published
                post.status = "published"
                post.platform_post_id = platform_post_id
                post.published_at = datetime.utcnow()
                post.error_message = None
                published_count += 1
                logger.info(f"Published post {post.id} on {post.platform} (post_id={platform_post_id})")

            except Exception as e:
                post.status = "failed"
                post.error_message = str(e)[:500]
                post.retry_count += 1
                failed_count += 1
                logger.error(f"Failed to publish post {post.id}: {e}")

            await db.commit()

        return {
            "published": published_count,
            "failed": failed_count,
            "total": len(due_posts),
        }


async def _publish_post(post: ScheduledPost, tenant: Tenant) -> str:
    """Publish a single post to FB or IG. Returns the platform post ID."""
    if post.platform == "facebook":
        return await _publish_to_facebook(post, tenant)
    elif post.platform == "instagram":
        return await _publish_to_instagram(post, tenant)
    else:
        raise Exception(f"Unknown platform: {post.platform}")


async def _publish_to_facebook(post: ScheduledPost, tenant: Tenant) -> str:
    """Publish to Facebook Page."""
    from app.scheduling.facebook_publisher import (
        publish_feed_post,
        publish_photo,
        publish_video,
    )

    if not tenant.page_access_token or not tenant.fb_page_id:
        raise Exception("Facebook Page not connected")

    if post.media_type == "text":
        result = await publish_feed_post(
            tenant.page_access_token,
            tenant.fb_page_id,
            message=post.caption,
            link=post.link,
        )
        return result.get("id", "")

    elif post.media_type == "photo" and post.media_urls:
        result = await publish_photo(
            tenant.page_access_token,
            tenant.fb_page_id,
            photo_url=post.media_urls[0],
            caption=post.caption,
        )
        return result.get("id", "")

    elif post.media_type == "video" and post.media_urls:
        result = await publish_video(
            tenant.page_access_token,
            tenant.fb_page_id,
            video_url=post.media_urls[0],
            title=post.caption[:100],
            description=post.caption,
        )
        return result.get("id", "")

    else:
        # Default to feed post
        result = await publish_feed_post(
            tenant.page_access_token,
            tenant.fb_page_id,
            message=post.caption,
        )
        return result.get("id", "")


async def _publish_to_instagram(post: ScheduledPost, tenant: Tenant) -> str:
    """Publish to Instagram."""
    from app.scheduling.instagram_publisher import (
        publish_image,
        publish_reel,
        publish_story,
    )

    if not tenant.ig_access_token or not tenant.ig_user_id:
        raise Exception("Instagram account not connected")

    if not post.media_urls:
        raise Exception("Instagram requires media (image or video)")

    media_url = post.media_urls[0]

    if post.media_type == "photo":
        result = await publish_image(
            tenant.ig_access_token,
            tenant.ig_user_id,
            image_url=media_url,
            caption=post.caption,
        )
        return result.get("id", "")

    elif post.media_type in ("video", "reel"):
        result = await publish_reel(
            tenant.ig_access_token,
            tenant.ig_user_id,
            video_url=media_url,
            caption=post.caption,
        )
        return result.get("id", "")

    elif post.media_type == "story":
        result = await publish_story(
            tenant.ig_access_token,
            tenant.ig_user_id,
            media_url=media_url,
            media_type="IMAGE" if post.media_type == "photo" else "VIDEO",
        )
        return result.get("id", "")

    else:
        raise Exception(f"Unsupported IG media_type: {post.media_type}")


def _run_async(coro):
    """Run an async coroutine from sync Huey context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
