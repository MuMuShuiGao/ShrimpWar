# 阶段一架构决策记录

> 2026-08-12 | 通过 /grill-me 逐个问题敲定

---

## 技术栈

| 维度 | 决策 | 理由 |
|---|---|---|
| Web 框架 | FastAPI | 异步原生、类型提示、天然适合管理子进程和文件 I/O |
| 前端 | Jinja2 + HTMX SSR | 阶段一不需要 SPA 的复杂度，SSR 够用 |
| CSS | Tailwind CLI standalone | 扫描 Jinja2 模板类名，编译输出到 `static/css/`，无 Vite/React |
| 数据库 | SQLite | 单文件、零配置、与自托管理念一致，以后可迁 PostgreSQL |

---

## 数据层

### agents 表（SQLite）

```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    avatar TEXT NOT NULL DEFAULT '',
    agent_key TEXT NOT NULL UNIQUE,
    workspace_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- `user_id` 阶段一写死为单用户（admin），不做认证系统
- DB 只存元数据索引，实际内容（System Prompt、配置等）存文件系统

### 工作区目录结构

```
workspaces/<agent_key>/
├── SOUL.md
├── IDENTITY.md
├── USER.md
├── AGENTS.md
├── TOOLS.md
├── MEMORY.md
├── BOOTSTRAP.md
├── HEARTBEAT.md
├── agent.config.json
└── skills/
```

- 创建 Agent 时全部 scaffold，有内容的写内容，没内容的空文件
- `agent_key` 由用户创建时手动填写，冲突提示"已被占用"

### agent.config.json schema

```json
{
  "agentId": "xxx",
  "name": "审稿员",
  "description": "负责审核技术文档质量",
  "platform": "claude-code",
  "avatar": "/avatars/crab.png",
  "providerId": "provider_deepseek",
  "apiKeys": { "OPENAI_API_KEY": "sk-..." },
  "model": "deepseek-chat",
  "temperature": 0.7,
  "maxTokens": 4096,
  "updatedAt": "2026-08-12T10:30:00Z"
}
```

- `apiKeys` 阶段一明文存储，安全问题后面统一处理

---

## 项目目录结构

```
app/
├── __init__.py
├── main.py              # FastAPI app + 生命周期
├── db.py                # SQLite 连接 + 表初始化
├── agents/              # Agent CRUD
│   ├── __init__.py
│   ├── models.py        # Pydantic schemas
│   ├── router.py        # HTML 路由（SSR 页面）
│   ├── api.py           # REST API 路由
│   └── service.py       # 业务逻辑层
├── runner/              # Agent Runner
│   ├── __init__.py
│   ├── manager.py       # 进程 Map 管理
│   └── process.py       # asyncio.subprocess 封装
├── workspace/           # 工作区文件操作
│   ├── __init__.py
│   └── scaffold.py      # 创建/读取工作区文件
├── templates/           # Jinja2 模板
│   ├── base.html
│   ├── agents/
│   │   ├── list.html
│   │   ├── detail.html
│   │   └── create.html
│   └── components/      # HTMX 组件片段
└── static/              # CSS/JS（Tailwind 编译输出）
```

---

## 路由

| 路由 | 用途 |
|---|---|
| `GET /` | 重定向到 `/agents` |
| `GET /agents` | Agent 列表页（窝） |
| `GET /agents/new` | 手动创建表单 |
| `POST /agents` | 创建 Agent（API） |
| `GET /agents/{agent_key}` | 详情编辑页 |
| `PUT /agents/{agent_key}` | 更新 Agent 配置（API） |
| `GET /agents/{agent_key}/status` | 状态轮询 API |

---

## Runner

### 进程管理方式

- `asyncio.create_subprocess_exec`（标准库，零依赖）
- 进程引用 + 状态标记存在内存 `dict[agent_id, ProcessRef]`

### 状态模型（One-shot 模式）

```
idle → running → idle（成功）
idle → running → error（失败）
```

- 前端每 2 秒轮询 `/api/agents/{id}/status`
- 整个周期几秒到一两分钟

### 启动命令（Claude Code）

```bash
claude -p "用户消息" --add-dir=<workspace_path> --output-format=json --no-chrome
```

- Runner 只传 `--workspace` 和 `--message` 给子进程
- 子进程自己读工作区文件（SOUL.md、agent.config.json、skills/）
- Runner 不替子进程拼 prompt、不传配置

---

## 编辑页 UI

- SOUL.md 编辑：裸 `<textarea>`，POST 回后端写文件
- agent.config.json 字段：标准 `<input>` 表单
- 阶段一不引入 Monaco/CodeMirror

---

## 三种创建方式（阶段一）

| 方式 | 状态 |
|---|---|
| 手动创建 | 实现 |
| 一键领养官方 Agent | 按钮置灰，标"开发中" |
| 上传本地 Agent 文件夹 | 按钮置灰，标"开发中" |

---

## 实现顺序

1. 项目骨架 — FastAPI app、SQLite 初始化、目录结构
2. Workspace 模块 — scaffold 工作区文件
3. Agents CRUD — 模型、API、页面（列表/创建/详情）
4. Runner — 进程封装 + 状态 API
5. 串起来 — 详情页启停 agent

---

## 已知债务

- `apiKeys` 明文存储 → 需敏感信息隔离
- 单用户模式 → 需认证系统
- `user_id` 写死 → 需多用户支持
