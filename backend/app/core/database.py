"""
Database configuration
MySQL / SQLite / PostgreSQL 자동 감지
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# DB 유형 판별
db_url = settings.DATABASE_URL
is_sqlite = db_url.startswith("sqlite")
is_mysql = "mysql" in db_url
is_postgres = "postgresql" in db_url or "postgres" in db_url

# 엔진 인자 구성
engine_kwargs = {
    "pool_pre_ping": True,
    "echo": settings.DEBUG,
}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
elif is_mysql:
    # MySQL 커넥션 풀 설정
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_recycle"] = 3600  # 1시간마다 커넥션 갱신
elif is_postgres:
    # PostgreSQL 커넥션 풀 설정
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_recycle"] = 1800  # 30분마다 커넥션 갱신

# SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# SQLite FK 지원 활성화
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base import (모든 모델이 이것을 상속)
from app.models.base import Base


def get_db():
    """
    Dependency for FastAPI routes
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
