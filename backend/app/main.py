r"""应用入口：装配 FastAPI、跨域、异常处理、路由与静态文件。

启动命令（在 backend/ 下）：

    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

启动时会连一次数据库做自检；连不上则进程直接起不来，便于尽早发现配置问题。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, bookings, devices, files, labs, users
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.result import Result
from app.core.storage import ensure_upload_dirs, public_root
from app.db import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动前连库自检，退出时释放连接池。"""
    await init_db()  # 启动自检：数据库可连接
    yield
    await close_db()


app = FastAPI(title="格物 · 实验室智能预约 API", version="0.1.0", lifespan=lifespan)

# 开发期前端直连 5173/5174；生产建议由 Nginx 同源代理，收紧 origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一响应信封与全局异常处理：404/405/422/500 都返回 {code,message,data}
register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(bookings.router)
app.include_router(devices.router)
app.include_router(files.router)
app.include_router(labs.router)
app.include_router(users.router)

# 公开文件（头像、实验室封面）直接静态托管；私有附件不挂载，走 /api/files/{id}/download 鉴权
ensure_upload_dirs()
app.mount("/media", StaticFiles(directory=public_root()), name="media")


# GET /hello 健康检查
# 不访问数据库、不需要登录，用于确认服务是否已启动。
#
# Returns:
#     Result[dict[str, str]]: code=200，data 为固定文案。
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
