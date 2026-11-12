from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.result import Result
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


@app.get("/hello", tags=["meta"], response_model=Result[dict[str, str]])
def hello() -> Result[dict[str, str]]:
    return Result.ok({"message": "FastAPI 工程运行中"})

