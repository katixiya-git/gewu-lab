from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth
from app.db import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # 启动自检：数据库可连接
    yield
    await close_db()


app = FastAPI(title="格物 · 实验室智能预约 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


@app.get("/hello", tags=["meta"])
def hello() -> dict[str, str]:
    return {"message": "FastAPI 工程运行中"}
