# 阶段二：单 Agent 聊天 — 架构决策记录

> 2026-08-12 | 通过 /grill-me 逐个问题敲定

---

## 技术决策

### 1. 实时通信协议：SSE

Server-Sent Events。聊天场景单向推流（服务器→浏览器），不需 WebSocket 的双向能力。

- FastAPI `StreamingResponse` 原生支持
- 前端 `EventSource` API，十几行 JS 搞定
- 比轮询省资源，比 WebSocket 少一半复杂度

### 2. 数据模型

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    title TEXT NOT NULL DEFAULT '新对话',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

设计要点：

- 一轮对话 = 两条 message（user + assistant），不存 JSON 数组。查询、分页、渲染都简单
- **不设 `status` 字段** — 流式状态是传输层的事，SSE 连接开着就是 streaming，关了就是结束，不需要 DB 记录这个瞬态
- 无 `user_id`，延续阶段一单用户模式
- 删除对话：**硬删除** `DELETE CASCADE`，阶段一不需要软删除的复杂度

### 3. 流式中转：asyncio.Queue

```
subprocess stdout → asyncio.Queue → SSE StreamingResponse → 浏览器
```

- Queue 挂 `RunnerManager`（`dict[conv_id, asyncio.Queue]`），process 和 queue 生命周期绑定
- 哨兵值 `None` 表示流结束
- 流结束时后端写 assistant message 到 DB

### 4. 路由

独立聊天页，不替换现有详情编辑页。配置和聊天是两种心智模式。

| 路由 | 用途 |
|---|---|
| `GET /agents/{agent_key}/chat` | 聊天主页（对话列表 + 最新对话） |
| `GET /agents/{agent_key}/chat/new` | 新建对话（点击即建，INSERT 后重定向） |
| `GET /agents/{agent_key}/chat/{conv_id}` | 进入历史对话 |
| `POST /api/agents/{agent_key}/chat/{conv_id}/stream` | 发消息，返回 SSE 流 |
| `DELETE /api/agents/{agent_key}/chat/{conv_id}` | 删除对话 |

详情页顶部加"对话"按钮跳转到 chat。

### 5. SSE 交互流程

两步分离：

```
POST 用户消息 → INSERT user message → 启动 claude 子进程 → 返回 201
         ↓
GET /api/.../stream → SSE 逐 chunk 推送 → 前端 EventSource 接收
         ↓
流结束 → 后端 INSERT assistant message（完整内容）
```

POST 之后前端立刻 GET SSE。启动空窗期通过 SSE 第一帧解决。

SSE 事件格式：

```
event: token
data: 回复文本\n

event: done
data: {"status": "complete"}\n

event: error
data: {"status": "error", "message": "..."}\n
```

前端用原生 `EventSource`，仅聊天交互写 JS，页面导航和其他交互仍用 HTMX。

### 6. 对话创建时机

**点击即建**。用户点"新对话" → 立即 INSERT → 重定向到 `/chat/{id}`。URL 立即确定，刷新不丢失。

### 7. 对话标题

首条用户消息前 30 字自动截取为 title，后续支持手动编辑（`contenteditable`，阶段一暂不实现）。

### 8. 聊天上下文

**携带最近 10 轮消息**拼入 `-p` 参数。最简单的方式，不引入 SDK 或 CLI 会话管理。

方案对比：
- CLI `--resume`/`--session-id`：参数依赖 CLI 版本，不可靠
- SDK：引入新依赖，改动过大
- 拼入 `-p`：零依赖，阶段一够用，上下文限制明确

### 9. Runner 流式化改造

`start_claude_code` 从 `communicate()` 改为逐行读 stdout + 推 Queue：

- CLI args 去掉 `--output-format=json`，读裸 stdout
- `asyncio.Queue` 由 SSE handler 创建，传引用给 `_stream_stdout` 协程
- 进程结束后 `put(None)` 通知 SSE 结束

### 10. 页面布局

左右分栏：左侧对话列表，右侧消息区 + 底部输入框。

```
┌─────────────────────────────────────────────┐
│  ← 返回  Agent名称    [+ 新对话]            │
├────────────┬────────────────────────────────┤
│ 对话列表    │                                │
│            │      聊天消息区                  │
│ · 对话1    │                                │
│ · 对话2    │   [输入框]                      │
│ · 对话3    │                                │
└────────────┴────────────────────────────────┘
```

---

## 已知债务

- 聊天上下文仅 10 轮 → 长对话需摘要或向量检索
- 对话标题手动编辑 → 阶段一未实现
- SSE 断开重连时消息去重 → 未处理
