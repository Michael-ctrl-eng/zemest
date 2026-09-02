"""Standalone Huey worker entry point.

Run as: ``python -m app.tasks.worker_main``

The API process embeds a consumer only when HUEY_INLINE_CONSUMER=true
(single-process mode). In the production compose, a DEDICATED worker
service runs this module instead — one consumer for the whole stack, so
queued tasks (crawl, notifications) execute exactly once no matter how
many API replicas exist.
"""
from __future__ import annotations

import logging
import signal
import threading

from app.config import get_settings
from app.tasks.huey_app import huey_app

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    settings = get_settings()

    if not settings.HUEY_ENABLED:
        logger.error("HUEY_ENABLED=false — worker exits (queue disabled)")
        return

    if huey_app.immediate:
        logger.error(
            "Huey immediate mode is ON — a dedicated worker is pointless "
            "(tasks execute inline). Set HUEY_IMMEDIATE=false."
        )
        return

    stop_event = threading.Event()

    def _sigterm(_signum, _frame):
        logger.info("SIGTERM received — draining worker")
        stop_event.set()

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    # Configure for a dedicated worker: more threads than the API's
    # embedded single-thread consumer (crawl + notifications can afford
    # 4 concurrent tasks on the worker box).
    from app.tasks.huey_app import _EmbeddedConsumer

    consumer = _EmbeddedConsumer(huey_app, workers=4)
    consumer.start()
    logger.info(
        "Huey dedicated worker started (workers=4, sqlite=%s)",
        settings.HUEY_SQLITE_PATH,
    )
    try:
        stop_event.wait()
    finally:
        consumer.stop()
        logger.info("Huey worker stopped")


if __name__ == "__main__":
    main()
