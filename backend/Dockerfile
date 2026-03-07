# ============================
# Backend Dockerfile
# FastAPI + Celery Worker
# ============================

FROM python:3.12-slim AS base

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 환경 변수 기본값
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# ============================
# FastAPI 서버 타겟
# ============================
FROM base AS fastapi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================
# Celery Worker 타겟
# ============================
FROM base AS celery-worker

# 모델 파일 디렉토리
RUN mkdir -p /app/models

CMD ["celery", "-A", "app.core.celery_app:celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=1", \
     "--pool=solo", \
     "-Q", "ai_inference,db_operations,default"]
