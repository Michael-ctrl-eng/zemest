"""Silent-trainer cycle — one scan/train pass, executed by APScheduler.

The 45-second loop that calls this lives in app/main.py's lifespan
(APScheduler job ``silent-trainer``), replacing the old hand-rolled
asyncio worker loop with the same contract:

  every 45 s  →  training_cycle_once() over all active tenants
              →  classify new conversations (junk vs commerce)
              →  rebuild style profile from commerce chats
              →  checkpoint state (crash-safe, resume-where-it-stopped)

Invisibility: this touches NO API surface and NO dashboard page. The only
trace is log lines in backend.log (operator-facing, not user-facing).

Resilience contract:
- one bad tenant cycle → logged, backoff recorded, cycle continues
  (handled inside app/ai/silent_trainer.py)
- whole process reaped → the platform's fetchWithHeal restarts the daemon
  and the next scheduled cycle resumes from the persisted training_state
  checkpoints

Enable/disable with SILENT_TRAINER_INLINE_WORKER (default on). Set it to
"false" if training moves to an external worker to avoid double-training.
"""
import logging

logger = logging.getLogger(__name__)


async def training_cycle_once() -> dict:
    """One scan/train cycle. Opens its own DB session (no request scope)."""
    from app.database import async_session
    from app.ai.silent_trainer import run_training_cycle_once

    async with async_session() as db:
        return await run_training_cycle_once(db)
