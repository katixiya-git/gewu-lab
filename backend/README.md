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

已为本项目 venv 配置阿里云镜像（`.venv/pip.ini`，`global.index-url = https://mirrors.aliyun.com/pypi/simple/`、超时 60s），装包会自动走镜像。

`requirements.txt` 锁定：fastapi 0.115.13、uvicorn 0.34.0、SQLAlchemy 2.0.41、PyMySQL 1.1.1、pydantic-settings 2.7.1。

如果连 MySQL 8 时报 `cryptography is required`，再补：`python -m pip install cryptography`。

开发工具与后续依赖（ruff / pytest / redis / langgraph 等）都写在文件注释里，用到再装。

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

## 启动（入口写好之后）

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

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

- 不提交 `.venv/`、`.env`、`data/`、`logs/`；
- 数据库变更走 `docs/` 下的 SQL 脚本，不手改线上表；
- 代码风格用 ruff（配置待补）。
