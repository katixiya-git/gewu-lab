"""应用配置：统一从 ``.env`` 或进程环境变量读取。

约定：环境变量名大写（如 ``DB_HOST``），字段名小写（``db_host``），
pydantic-settings 负责大小写不敏感映射；本地开发把值写在 ``backend/.env``，
部署时用环境变量覆盖，不要把密码提交进仓库。
"""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全部配置项的声明式定义。"""

    # env_file 相对「启动进程的工作目录」解析（本项目是 backend/）
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- MySQL 连接 ----
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "gewu"

    # ---- JWT ----
    # 本地默认值仅供开发；上线务必通过 JWT_SECRET 覆盖
    jwt_secret: str = "gewu-local-dev-secret-please-change"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720  # 12 小时

    # ---- 文件上传 ----
    # upload_dir 相对 backend 运行目录；public 子目录直接静态托管
    upload_dir: str = "uploads"
    upload_max_mb: int = 20  # 单文件大小上限

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
        """兼容两种写法：JSON 数组，或 ``a,b,c`` 逗号分隔字符串。

        环境变量只能传字符串，这里在类型校验前先拆开；如果已经是列表
        （如测试里直接构造 Settings）则原样返回。
        """
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def database_url(self) -> str:
        """拼出 SQLAlchemy 异步连接串（aiomysql 驱动）。

        密码里可能有 ``@``、``/`` 等字符，必须 ``quote_plus`` 转义，
        否则连接串会被解析错位。
        """
        password = quote_plus(self.db_password)
        return (
            f"mysql+aiomysql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    """进程内单例：只解析一次 .env，避免每个请求重复读文件。"""
    return Settings()
