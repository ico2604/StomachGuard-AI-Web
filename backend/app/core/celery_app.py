"""
Celery Application Configuration
Redis를 브로커 겸 결과 백엔드로 사용
"""

from celery import Celery
import os

# .env 로딩 (워커에서 직접 실행될 때를 위해)
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "gastric_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

# Celery 설정
celery_app.conf.update(
    # 직렬화
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 타임존
    timezone="Asia/Seoul",
    enable_utc=True,
    
    # 결과 만료 (1시간)
    result_expires=3600,
    
    # 워커 설정
    worker_prefetch_multiplier=1,  # 배칭 사용 시 1로 설정
    task_acks_late=True,           # 태스크 완료 후 ACK
    
    # 태스크 라우팅
    task_routes={
        "app.worker.tasks.predict_single": {"queue": "ai_inference"},
        "app.worker.tasks.save_diagnosis_result": {"queue": "db_operations"},
    },
    
    # 기본 큐
    task_default_queue="default",
    
    # 재시도
    task_annotations={
        "app.worker.tasks.predict_single": {
            "rate_limit": "100/m",
            "max_retries": 2,
            "default_retry_delay": 5,
        },
    },
)
