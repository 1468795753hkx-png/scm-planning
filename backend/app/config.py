"""应用配置：从环境变量读取，默认开发值。"""
import os
from dataclasses import dataclass
from pathlib import Path

# 尝试加载 .env（若安装了 python-dotenv）
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except Exception:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./scm.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
    # CORS 白名单（逗号分隔）；生产务必覆盖真实前端域名
    allowed_origins: tuple = tuple(
        o.strip() for o in os.getenv("ALLOWED_ORIGINS",
                                     "http://127.0.0.1:8080,http://localhost:8080").split(",") if o.strip()
    )


def get_settings() -> Settings:
    return Settings()