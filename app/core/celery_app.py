"""작업 큐(Celery) 접속점. api 프로세스는 여기서 가져온 celery_app으로 작업을 큐에 넣고(.delay()),
worker 프로세스는 `celery -A app.core.celery_app worker`로 이 객체를 보고 큐를 소비한다.
두 프로세스가 같은 Redis(broker)를 보게 하는 게 이 파일의 핵심 역할."""
from celery import Celery

from app.core.config import settings

celery_app = Celery("doni", broker=settings.redis_url, backend=settings.redis_url)
celery_app.autodiscover_tasks(["app.domains.pipelines"])
