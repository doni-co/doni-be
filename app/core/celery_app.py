from celery import Celery

from app.core.config import settings

celery_app = Celery("doni", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.domains.pipelines.tasks.*": {"queue": "pipelines"}}
celery_app.autodiscover_tasks(["app.domains.pipelines"])
