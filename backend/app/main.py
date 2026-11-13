from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, files, users
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.result import Result
from app.core.storage import ensure_upload_dirs, public_root
from app.db import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # 启动自检：数据库可连接
    yield
    await close_db()


app = FastAPI(title="格物 · 实验室智能预约 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(files.router)
app.include_router(users.router)

# 公开文件（头像、实验室封面）直接静态托管；私有附件不挂载，走鉴权下载
ensure_upload_dirs()
app.mount("/media", StaticFiles(directory=public_root()), name="media")


@app.get(
    "/hello",
    tags=["meta"],
    response_model=Result[dict[str, str]],
    summary="健康检查",
    description="不访问数据库、不需要登录，用于确认服务是否已启动。",
)
def hello() -> Result[dict[str, str]]:
    """返回固定文案，供启动自检和前端联调使用。"""
    return Result.ok({"message": "FastAPI 工程运行中"})

