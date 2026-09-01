"""In-process silent-trainer worker — runs the self-training loop WITHOUT
Celery/Redis, exactly like the inline scheduler worker.

  every 45 s  →  run_training_cycle_once() over all active tenants
              →  classify new conversations (junk vs commerce)
              →  rebuild style profile from commerce chats
              →  checkpoint state (crash-safe, resume-where-it-stopped)

Invisibility: this touches NO API surface and NO dashboard page. The only
trace is log lines in backend.log (operator-facing, not user-facing).

Resilience contract:
- one bad tenant cycle → logged, backoff recorded, loop continues
- the loop task itself can never raise (per-cycle try/except)
- whole process reaped → the platform's fetchWithHeal restarts the daemon
  and this loop resumes from the persisted training_state checkpoints

Enable/disable with SILENT_TRAINER_INLINE_WORKER (default on). Set it to
"false" if you move training to a Celery beat deployment to avoid
double-training.
"""
import asyncio
import logging

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None

CYCLE_INTERVAL_SECONDS = 45.0


async def _training_cycle_once() -> dict:
    """One scan/train cycle. Opens its own DB session (no request scope)."""
    from app.database import async_session
    from app.ai.silent_trainer import run_training_cycle_once

    async with async_session() as db:
        return await run_training_cycle_once(db)


async def _worker_loop():
    logger.info("Silent trainer worker started (interval=%ss)", CYCLE_INTERVAL_SECONDS)
    # Let the app finish booting (incl. column migrations) first
    await asyncio.sleep(8)
    while True:
        try:
            result = await _training_cycle_once()
            if result and (result.get("classified") or result.get("profiles_built") or result.get("errors")):
                logger.info("Silent trainer cycle: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never let one bad cycle kill the trainer
            logger.exception("Silent trainer worker cycle failed")
        await asyncio.sleep(CYCLE_INTERVAL_SECONDS)


def start_inline_trainer(app) -> None:
    """Start the background training loop unless disabled or already running."""
    global _worker_task
    if not str(getattr(settings, "SILENT_TRAINER_INLINE_WORKER", True)).lower() in (
        "1", "true", "yes", "on",
    ):
        logger.info("Silent trainer worker disabled via SILENT_TRAINER_INLINE_WORKER")
        return
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.get_event_loop().create_task(_worker_loop())


def stop_inline_trainer() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
    _worker_task = None
