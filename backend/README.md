# 格物后端（FastAPI）

格物 · 实验室智能预约平台的后端服务，负责预约业务、LangGraph 对话编排与 Redis 向量检索。

当前状态：账号、实验室、设备、预约、文件上传、知识库检索与 AI 对话（LangGraph + SSE）均已实现，
`pytest` 49 passed / 3 skipped（跳过的 3 个需要 `GEWU_TEST_REDIS_URL` 指向真实 Redis Stack）。

## 目录

```
backend/
├── app/                 # 应用代码（api / services / models / schemas / core / ai / knowledge）
├── tests/               # pytest 用例（pytest.ini 里 asyncio_mode = auto）
├── scripts/             # 运维 / 数据脚本（建表、造数据、建知识库、冒烟）
├── uploads/             # 上传文件（已忽略；public/ 走 /media，private/ 走鉴权下载）
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

# 一次装齐（版本已锁定在 requirements.txt）
python -m pip install -r requirements.txt
```

已为本项目 venv 配置阿里云镜像（`.venv/pip.ini`，`global.index-url = https://mirrors.aliyun.com/pypi/simple/`、超时 60s），装包会自动走镜像。

`requirements.txt` 分三块锁定：Web 基础（fastapi 0.115.13、uvicorn 0.34.0、SQLAlchemy 2.0.41、
PyMySQL 1.1.1、aiomysql 0.3.2、pydantic-settings 2.7.1、bcrypt 4.2.1、PyJWT 2.10.1）、
知识库（redis 6.4.0、openai 1.109.1）、AI 编排（langchain 1.5.0、langgraph 1.2.21、
langgraph-checkpoint-redis 0.6.0 等）。

如果连 MySQL 8 时报 `cryptography is required`，再补：`python -m pip install cryptography`。

开发工具（pytest 等）在 `requirements-dev.txt` 里，按需安装。

## 配置

```powershell
Copy-Item .env.example .env
```

然后按需修改 `.env`：数据库连接、Redis 地址、模型 Key。`.env` 已被忽略，不要提交。

### AI 与 Redis 配置

AI 对话用百炼 qwen（OpenAI 兼容接口），会话状态（LangGraph checkpoint）存 Redis Stack：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AI_ENABLED` | `true` | 关闭后 `/api/ai/*` 返回 503，便于无 Key 环境跑业务测试 |
| `AI_BASE_URL` | 百炼 compatible-mode 地址 | OpenAI 兼容接口根地址 |
| `AI_API_KEY` | 空 | 百炼 API Key；留空时 `ai_ready=false` |
| `AI_MODEL` | `qwen-plus` | 对话模型 |
| `AI_TEMPERATURE` | `0.2` | 工具调用场景建议低温 |
| `AI_TIMEOUT_SECONDS` | `60` | 单次模型请求超时 |
| `AI_MAX_HISTORY_MESSAGES` | `20` | 每次请求最多携带的历史消息条数 |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis 地址；虚拟机 Redis Stack 用 `redis://your-redis-host:6379/0` |
| `REDIS_PASSWORD` | 空 | 未设密码留空；设了密码会先 AUTH |
| `AI_THREAD_TTL_SECONDS` | `86400` | 会话空闲过期时间（秒） |
| `AI_CHECKPOINT_PREFIX` | `gewu:ai` | checkpoint key 前缀 |

### 文件上传配置

| 变量 | 默认 | 说明 |
|---|---|---|
| `UPLOAD_DIR` | `uploads` | 上传根目录，相对启动目录（`backend/`）；`public/` 由 `/media` 静态托管，`private/` 走 `/api/files/{id}/download` 鉴权 |
| `UPLOAD_MAX_MB` | `20` | 单文件大小上限（MB），超出直接 400 |

落盘规则见 `app/core/storage.py`：后缀白名单 + 文件头魔数双校验，文件名一律 uuid
（原始文件名只入库供下载回显），避免路径穿越与重名覆盖。`uploads/` 不入库。

## 启动

首次运行前先建表并造一批种子数据（都是幂等脚本，可重复跑）：

```powershell
.venv\Scripts\python.exe -m scripts.init_db      # 建表
.venv\Scripts\python.exe -m scripts.seed_users    # 管理员/学生账号
.venv\Scripts\python.exe -m scripts.seed_labs     # 实验室
.venv\Scripts\python.exe -m scripts.seed_devices  # 设备
```

然后起服务（启动时用 `SELECT 1` 做连库自检，连不上进程直接退出）：

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

接口文档在 `http://127.0.0.1:8000/docs`，健康检查 `GET /hello`（不连库、不需要登录）。

## 知识库检索

`docs/knowledge/` 下的 Markdown 语料会被切成 500 字左右的块，用百炼 `text-embedding-v3`
生成 1024 维向量，写入 Redis Stack 的 HNSW 索引（只做向量检索，中文全文分词不可用）。

```bash
cd backend
.\.venv\Scripts\python.exe -m scripts.build_kb --dry-run   # 只看切块结果，不联网
.\.venv\Scripts\python.exe -m scripts.build_kb             # 全量重建索引
.\.venv\Scripts\python.exe -m scripts.kb_smoke             # 5 个固定问题 + 延迟
```

需要配置 `REDIS_URL`（指向 Redis Stack 的 0 号库，索引不能建在其它库）、`REDIS_PASSWORD`
（无密码留空）与 `AI_API_KEY`（百炼 Key）。接口：

- `POST /api/knowledge/search`，body `{"query": "...", "topK": 3}`，返回
  `{docId, docTitle, section, content, similarity}` 列表（需登录）。
- `AI_ENABLED=false` 或未配置 Key → 503；索引为空 → 503（先跑 `scripts.build_kb`）；
  向量化失败 → 502；Redis 不可达 → 503。

## 约定

- 不提交 `.venv/`、`.env`、`uploads/`、`data/`、`logs/`；
- 数据库变更走 `docs/` 下的 SQL 脚本，不手改线上表；
- 代码风格用 ruff（配置待补）。
