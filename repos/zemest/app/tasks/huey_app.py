"""Huey task queue — SQLite-native, zero external broker.

Replaces the previous Celery+Redis setup (dead weight in this single-process
deployment: no Redis was ever provisioned, so every ``.delay()`` call failed
over to inline execution anyway — roadmap R3). What Huey adds for real:

* durable task queue in a SQLite file (``HUEY_SQLITE_PATH``) — survives
  process restarts, no broker to run
* automatic retries with backoff (``retries=``/``retry_delay=`` on tasks)
* an optional embedded worker (``HUEY_INLINE_CONSUMER``) running as threads
  INSIDE the uvicorn process — the single-process design (G4) preserved:
  no fork, no signal-handler clobbering (uvicorn keeps owning SIGTERM).

Periodic jobs (post publishing, weekly personality rebuild, silent trainer)
are NOT handled here — APScheduler owns them inside the uvicorn lifespan
(app/main.py), so the embedded consumer runs with ``periodic=False``.

Enqueue semantics: calling a ``@huey_app.task()``-decorated function ENQUEUES
it and returns a ``Result``. With ``HUEY_ENABLED=false`` the app instance is
``immediate`` — calling a task runs it synchronously (tests/debugging).

Huey 3.x notes (verified against huey 3.3.4):
* the sqlite path kwarg is ``filename=`` (NOT ``path=`` — that leaks into
  ``sqlite3.connect(**conn_kwargs)`` and TypeErrors),
* ``Consumer.start()`` registers process signal handlers — we subclass to
  skip that (uvicorn owns the signals) and start the worker threads directly.
"""
import logging

from huey import SqliteHuey

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

huey_app = SqliteHuey(
    "zemest",
    filename=settings.HUEY_SQLITE_PATH,
    # Tests / HUEY_ENABLED=False → execute tasks synchronously on call.
    immediate=not settings.HUEY_ENABLED,
)

# Import task modules so their @huey_app.task registrations happen at startup
# (mirrors the old celery beat import contract).
import app.tasks.crawl_tasks  # noqa: F401, E402
import app.tasks.notification_tasks  # noqa: F401, E402
import app.tasks.scheduling_tasks  # noqa: F401, E402
import app.tasks.style_tasks  # noqa: F401, E402

# ---------------------------------------------------------------------------
# Embedded consumer (optional) — 1 worker THREAD inside this process, no
# periodic jobs (APScheduler owns those). Never touches signal handlers.
# ---------------------------------------------------------------------------
_consumer = None  # huey.consumer.Consumer handle


class _EmbeddedConsumer:
    """Signal-safe wrapper around huey 3.x's Consumer.

    huey's own ``Consumer.start()`` calls ``signal.signal(SIGTERM, ...)`` —
    which would clobber uvicorn's graceful-drain handler. We start the
    scheduler/worker threads the same way but leave every signal alone.
    """

    def __init__(self, huey, workers: int = 1):
        from huey.consumer import Consumer

        # periodic=False: APScheduler (lifespan) owns periodic jobs.
        self._impl = Consumer(huey, workers=workers, periodic=False)

    def start(self) -> None:
        self._impl._set_signal_handlers = lambda: None  # uvicorn owns signals
        self._impl.start()

    def stop(self) -> None:
        self._impl.stop()

    def is_running(self) -> bool:
        try:
            return any(
                proc.is_alive() for _, proc in self._impl.worker_threads
            )
        except Exception:
            return False


def start_huey_consumer() -> bool:
    """Start the embedded 1-worker consumer if enabled.

    Returns True when a consumer is (already) running. Any failure logs and
    returns False — callers then use their inline fallback, so a broken
    consumer can never take the API down.
    """
    global _consumer
    if not settings.HUEY_ENABLED or not settings.HUEY_INLINE_CONSUMER:
        logger.info(
            "Huey inline consumer disabled (HUEY_ENABLED=%s HUEY_INLINE_CONSUMER=%s)",
            settings.HUEY_ENABLED, settings.HUEY_INLINE_CONSUMER,
        )
        return False
    if huey_app.immediate:
        logger.info("Huey immediate mode — tasks execute inline, no consumer")
        return False
    if _consumer is not None and _consumer.is_running():
        return True
    try:
        c = _EmbeddedConsumer(huey_app, workers=1)
        c.start()
        _consumer = c
        logger.info(
            "Huey embedded consumer started (workers=1, sqlite=%s)",
            settings.HUEY_SQLITE_PATH,
        )
        return True
    except Exception:
        logger.exception("Huey embedded consumer failed to start — inline fallback active")
        _consumer = None
        return False


def stop_huey_consumer() -> None:
    """Stop the embedded consumer (app shutdown)."""
    global _consumer
    if _consumer is None:
        return
    try:
        _consumer.stop()
    except Exception:
        logger.exception("Huey consumer stop failed")
    _consumer = None


def huey_consumer_running() -> bool:
    """True only when a real consumer will pick up queued tasks soon.

    ``immediate`` mode is excluded on purpose: there, calling a task runs it
    synchronously (blocking) — callers (api/crawl.py, agent.py) prefer their
    own async inline fallbacks in that case instead of a blocking call.

    Two deployment shapes return True:

    * single-process — the embedded consumer (HUEY_INLINE_CONSUMER) is
      running in THIS process;
    * multi-service — HUEY_EXTERNAL_WORKER=True announces that a dedicated
      worker container consumes the shared queue file (HUEY_SQLITE_PATH on
      a shared volume), so enqueueing here is safe and durable.
    """
    if huey_app.immediate:
        return False
    if getattr(settings, "HUEY_EXTERNAL_WORKER", False):
        return True
    return _consumer is not None and _consumer.is_running()
