"""
Application configuration

모든 민감한 설정값은 backend/.env 파일에서 관리합니다.
.env 파일이 없으면 서버 시작 시 ValidationError가 발생합니다.

.env 생성 방법:
    cp .env.example .env
    # 이후 SECRET_KEY, ENCRYPTION_KEY 등을 실제 값으로 변경
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from typing import List, Optional
import os


class Settings(BaseSettings):
    # 프로젝트 정보
    PROJECT_NAME: str = "Gastric Hospital Backend"
    VERSION: str = "3.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 환경
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # 데이터베이스 (PostgreSQL for Docker, MySQL for local)
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/gastric_hospital"
    
    # JWT 설정 (반드시 .env에서 설정)
    SECRET_KEY: str  # 기본값 없음 -> .env 필수
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 암호화 (반드시 .env에서 설정)
    ENCRYPTION_KEY: str  # 기본값 없음 -> .env 필수
    
    # CORS - CORS_ORIGINS 또는 BACKEND_CORS_ORIGINS 둘 다 지원
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    BACKEND_CORS_ORIGINS: Optional[List[str]] = None  # 호환성용 별칭
    
    # 서버
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # AI 모델
    AI_MODEL_PATH: str = "mtl_best.pth"
    AI_DEVICE: str = "cuda"  # cuda or cpu
    
    # ==================== Celery + Redis ====================
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # Dynamic Batching
    BATCH_SIZE: int = 8
    BATCH_TIMEOUT_MS: int = 100  # milliseconds
    
    # Celery Worker
    CELERY_WORKER_CONCURRENCY: int = 1  # GPU 사용 시 1 권장
    
    @model_validator(mode="after")
    def merge_cors_origins(self) -> "Settings":
        """BACKEND_CORS_ORIGINS가 설정되면 CORS_ORIGINS로 병합"""
        if self.BACKEND_CORS_ORIGINS:
            # BACKEND_CORS_ORIGINS 값으로 덮어쓰기
            self.CORS_ORIGINS = self.BACKEND_CORS_ORIGINS
        return self
    
    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        placeholder_keywords = ["your-", "change-this", "example", "placeholder"]
        if any(kw in v.lower() for kw in placeholder_keywords):
            raise ValueError(
                "SECRET_KEY가 placeholder 값입니다. "
                ".env 파일에 실제 랜덤 키를 설정하세요.\n"
                "생성 방법: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY가 너무 짧습니다 (현재 {len(v)}자). "
                "최소 32자 이상의 랜덤 문자열을 사용하세요."
            )
        return v

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
