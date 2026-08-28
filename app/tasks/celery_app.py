from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "zemest",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Cairo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    worker_max_tasks_per_child=50,
    # Beat schedule — periodic background jobs
    beat_schedule={
        # Rebuild every tenant's per-page personality (style + knowledge)
        # from chat history once a week, Sunday 03:00 Cairo time.
        "rebuild-personality-weekly": {
            "task": "app.tasks.style_tasks.rebuild_all_personalities",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),
        },
        # Publish scheduled social media posts — runs every minute
        "publish-scheduled-posts": {
            "task": "publish_scheduled_posts",
            "schedule": crontab(minute="*"),
        },
    },
)

# Explicitly import tasks so Celery registers them at startup
import app.tasks.crawl_tasks  # noqa: F401, E402
import app.tasks.notification_tasks  # noqa: F401, E402
import app.tasks.style_tasks  # noqa: F401, E402
import app.tasks.scheduling_tasks  # noqa: F401, E402
