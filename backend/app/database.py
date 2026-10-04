"""数据库引擎与会话。MVP 默认 SQLite，生产切换 PostgreSQL。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表（开发便捷用；生产建议用 Alembic 迁移）。"""
    from . import models  # noqa: F401  确保模型已注册
    Base.metadata.create_all(bind=engine)