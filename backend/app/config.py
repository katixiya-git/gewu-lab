from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从 .env / 环境变量读取配置，字段名大小写不敏感（DB_HOST 等）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "gewu"

    jwt_secret: str = "gewu-local-dev-secret-please-change"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # 允许跨域的前端来源；环境变量 CORS_ORIGINS 可用逗号分隔覆盖
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def database_url(self) -> str:
        """SQLAlchemy 异步连接串（aiomysql 驱动）。"""
        password = quote_plus(self.db_password)
        return (
            f"mysql+aiomysql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
