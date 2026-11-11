# 格物后端（FastAPI）

格物 · 实验室智能预约平台的后端服务，负责预约业务、LangGraph 对话编排与 Redis 向量检索。

当前状态：**只完成工程初始化，尚未编写业务代码。**

## 目录

```
backend/
├── app/                 # 应用代码（待编写）
├── tests/               # 测试（待编写）
├── scripts/             # 运维 / 数据脚本（待编写）
├── .env.example         # 环境变量模板
├── requirements.txt     # 运行依赖
├── requirements-dev.txt # 开发依赖
└── .venv/               # 虚拟环境（已创建，不入库）
```

## 环境

- Python 3.12.9
- 虚拟环境已创建：`backend/.venv`

## 安装依赖

在 `backend` 目录下执行：

```powershell
# 激活虚拟环境
.venv\Scripts\Activate.ps1

# 当前阶段只装这 5 个（版本已锁定）
python -m pip install -r requirements.txt
```

`requirements.txt` 锁定：fastapi 0.115.13、uvicorn 0.34.0、SQLAlchemy 2.0.41、PyMySQL 1.1.1、pydantic-settings 2.7.1。

如果连 MySQL 8 时报 `cryptography is required`，再补：`python -m pip install cryptography`。

开发工具与后续依赖（ruff / pytest / redis / langgraph 等）都写在文件注释里，用到再装。

## 配置

```powershell
Copy-Item .env.example .env
```

然后按需修改 `.env`：数据库连接、Redis 地址、模型 Key。`.env` 已被忽略，不要提交。

## 启动（入口写好之后）

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 约定

- 不提交 `.venv/`、`.env`、`data/`、`logs/`；
- 数据库变更走 `docs/` 下的 SQL 脚本，不手改线上表；
- 代码风格用 ruff（配置待补）。
