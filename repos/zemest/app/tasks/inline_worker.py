"""In-process scheduler worker — publishes due posts WITHOUT Celery/Redis.

The Celery beat pipeline (app/tasks/scheduling_tasks.py + Redis) is the
production-scale option, but this deployment runs a single FastAPI process,
so we run the same publish loop as an asyncio background task inside the
uvicorn process:

  every 30 s  →  find posts with status='scheduled' AND scheduled_at <= now
              →  publish via the real FB/IG Graph API
              →  update status to published/failed (+ real error message)

Enable/disable with SCHEDULER_INLINE_WORKER (default on). If you later deploy
Celery + Redis, set it to "false" to avoid double-publishing.
"""
import asyncio
import logging

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def _publish_due_posts_once() -> dict:
    """One scan/publish cycle. Reuses the exact same publishing code path as
    the Celery task so both deployment modes behave identically."""
    from app.tasks.scheduling_tasks import _publish_due_posts_async

    return await _publish_due_posts_async()


async def _worker_loop():
    logger.info("Inline scheduler worker started (interval=30s)")
    # Small delay so the app finishes booting (incl. migrations) first
    await asyncio.sleep(5)
    while True:
        try:
            result = await _publish_due_posts_once()
            if result and result.get("total"):
                logger.info(f"Scheduler worker: {result}")
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never let one bad cycle kill the worker
            logger.exception("Scheduler worker cycle failed")
        await asyncio.sleep(30)


def start_inline_scheduler(app) -> None:
    """Start the background publish loop unless disabled or already running."""
    global _worker_task
    if not str(getattr(settings, "SCHEDULER_INLINE_WORKER", True)).lower() in ("1", "true", "yes", "on"):
        logger.info("Inline scheduler worker disabled via SCHEDULER_INLINE_WORKER")
        return
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.get_event_loop().create_task(_worker_loop())


def stop_inline_scheduler() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
    _worker_task = None
