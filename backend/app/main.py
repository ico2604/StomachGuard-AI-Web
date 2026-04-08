"""
FastAPI Main Application
위암 분류 병원 관리 시스템 - Phase 2
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.api.api_v1.api import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    redirect_slashes=False,  # 307 리다이렉트 방지 (프록시 환경에서 토큰 유실 문제)
)


class TrailingSlashMiddleware(BaseHTTPMiddleware):
    """
    Trailing slash 미들웨어
    /visits 요청이 오면 /visits/ 로 내부적으로 변환하여 처리
    (307 리다이렉트 대신 서버 내부에서 rewrite)
    
    동작 방식:
      - /api/v1/visits → /api/v1/visits/  (목록 엔드포인트)
      - /api/v1/visits/123 → 그대로 유지  (상세 엔드포인트)
      - /api/v1/auth/login → 그대로 유지  (action 엔드포인트)
    """
    # trailing slash가 불필요한 마지막 세그먼트 패턴
    # (숫자 ID, 특정 action 이름 등)
    SKIP_SEGMENTS = {"login", "me", "refresh", "diagnose", "stats", "summary",
                     "model-info", "openapi.json", "docs", "redoc", "predict",
                     "health"}

    async def dispatch(self, request: Request, call_next):
        path = request.scope["path"]
        if (
            path.startswith("/api/")
            and not path.endswith("/")
        ):
            last_segment = path.rstrip("/").split("/")[-1]
            # 숫자 ID, UUID/Celery task ID(하이픈 포함), action 엔드포인트는 건드리지 않음
            if (
                not last_segment.isdigit()
                and "-" not in last_segment  # UUID/Celery task ID
                and last_segment not in self.SKIP_SEGMENTS
                and "." not in last_segment
            ):
                request.scope["path"] = path + "/"
        response = await call_next(request)
        return response


# 미들웨어 등록 순서 중요: 먼저 등록한 것이 바깥에서 감쌈
# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trailing slash 미들웨어 (CORS 안쪽에서 동작)
app.add_middleware(TrailingSlashMiddleware)

# API 라우터 등록
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    """루트 경로"""
    return {
        "message": "위암 분류 병원 관리 시스템 API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "redoc": f"{settings.API_V1_STR}/redoc"
    }


@app.get("/health")
def health_check():
    """헬스 체크"""
    return {"status": "ok"}
