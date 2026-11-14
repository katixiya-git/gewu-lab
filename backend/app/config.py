"""应用配置：统一从 ``.env`` 或进程环境变量读取。

约定：环境变量名大写（如 ``DB_HOST``），字段名小写（``db_host``），
pydantic-settings 负责大小写不敏感映射；本地开发把值写在 ``backend/.env``，
部署时用环境变量覆盖，不要把密码提交进仓库。
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, field_validator
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

    # ---- AI 模型（百炼 qwen，OpenAI 兼容接口）----
    # 关闭后 /api/ai/* 统一返回 503，便于没有 key 的环境跑业务测试
    ai_enabled: bool = True
    # 显式用 AI_ 前缀，避免误读系统里其它工具设置的 OPENAI_API_KEY
    ai_api_key: str = ""
    ai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_model: str = "qwen-plus"
    # 工具调用场景要稳定，温度调低；范围 0~2
    ai_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    ai_timeout_seconds: int = 60
    # 预留项：历史上是「每次请求最多带多少条历史消息」。现在历史由
    # LangGraph 存在 Redis 里按 thread_id 自动读写，这个值已不参与逻辑。
    ai_max_history_messages: int = 20

    # ---- AI 会话状态（LangGraph checkpoint 存 Redis Stack）----
    # 注意：这里的 Redis 要装 Redis Stack（带向量检索模块），
    # 因为对话存档和知识库索引都靠它。
    redis_url: str = "redis://127.0.0.1:6379/0"
    # 为空表示 Redis 未设密码；有密码时客户端会先 AUTH
    redis_password: str = ""
    # 预留项：会话空闲多久过期（秒）。当前代码没有把它传给 checkpointer，
    # 所以存档不会自动过期，需要清理时得手工删 gewu:ai:* 开头的 key。
    ai_thread_ttl_seconds: int = 86400
    # Redis 里 checkpoint 的 key 前缀，便于和业务缓存区分
    ai_checkpoint_prefix: str = "gewu:ai"

    # ---- 知识库（Redis Stack 向量检索）----
    kb_index_name: str = "idx:gewu_kb"
    kb_key_prefix: str = "gewu:kb:"
    # 相对仓库根目录；build_kb.py 会解析成绝对路径
    kb_docs_dir: str = "docs/knowledge"
    kb_chunk_size: int = Field(default=500, ge=100, le=2000)
    kb_chunk_overlap: int = Field(default=80, ge=0, le=500)
    kb_top_k: int = Field(default=5, ge=1, le=10)
    kb_min_similarity: float = Field(default=0.20, ge=0.0, le=1.0)
    kb_embedding_model: str = "text-embedding-v3"
    kb_embedding_dim: int = Field(default=1024, ge=64, le=4096)
    kb_embed_batch_size: int = Field(default=10, ge=1, le=64)

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

    @property
    def ai_ready(self) -> bool:
        """AI 是否可用：开关打开，且确实配置了 API Key。

        路由层用它做快速失败，避免没配 key 时还把请求送进模型调用。
        """
        return self.ai_enabled and bool(self.ai_api_key.strip())

    @property
    def kb_docs_path(self) -> Path:
        """语料目录的绝对路径。

        ``kb_docs_dir`` 默认相对仓库根目录（backend/app → backend → 仓库根），
        传入绝对路径时原样返回，便于测试指向临时目录。
        """
        path = Path(self.kb_docs_dir)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path


@lru_cache
def get_settings() -> Settings:
    """进程内单例：只解析一次 .env，避免每个请求重复读文件。"""
    return Settings()
