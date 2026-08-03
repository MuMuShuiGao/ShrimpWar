# 阶段 4：团队 + Architectures — 架构决策记录

## 概述

阶段 4 目标：在画布上拖两个 Agent 连成一条线 → 输入任务 → 两个 Agent 依次执行 → 看到最终产出。

MVP 范围：**手动画布 + 链式执行**，不含 NL→DSL 生成，不含条件分支/并行。

---

## 决策清单

### 1. 画布技术

**选型**：Rete.js vanilla 版，通过 CDN 加载，无打包器依赖。

**原因**：项目是 Jinja2 SSR + HTMX，无 React/Vue/打包器。Rete.js 核心框架无关，CDN 直接加载即可。

**文件位置**：画布逻辑集中在 `app/static/js/canvas.js`，Jinja2 模板通过 `<script>` 引用。

### 2. DSL 格式

**格式**：JSON node+edge 结构，与画布导出数据**同一套格式**，无翻译层。

**示例**（串行链模板）：

```json
{
  "schemaVersion": "1.0",
  "name": "串行链团队",
  "description": "确定路径的逐步处理",
  "entryNodeId": "chain-start",
  "nodes": [
    {
      "id": "chain-start",
      "type": "start",
      "label": "用户输入",
      "outputKey": "user_task",
      "position": { "x": 60, "y": 240 }
    },
    {
      "id": "chain-analysis",
      "type": "agent",
      "label": "分析节点",
      "role": "理解任务并拆解要求",
      "kind": "worker",
      "agentInstanceId": null,
      "inputTemplate": "协作身份：执行者\n期望输入：用户任务\n期望输出：任务拆解\n\n{{upstream_outputs}}",
      "outputKey": "chain_analysis_output",
      "isManager": false,
      "position": { "x": 300, "y": 220 }
    },
    {
      "id": "chain-worker",
      "type": "agent",
      "label": "执行节点",
      "role": "根据拆解完成主要工作",
      "kind": "worker",
      "agentInstanceId": null,
      "inputTemplate": "协作身份：执行者\n期望输入：任务拆解\n期望输出：执行结果\n\n{{upstream_outputs}}",
      "outputKey": "chain_worker_output",
      "isManager": false,
      "position": { "x": 560, "y": 220 }
    },
    {
      "id": "chain-summary",
      "type": "agent",
      "label": "汇总节点",
      "role": "整理最终答复",
      "kind": "aggregator",
      "agentInstanceId": null,
      "inputTemplate": "协作身份：汇总者\n期望输入：执行结果\n期望输出：最终结果\n\n{{upstream_outputs}}",
      "outputKey": "chain_summary_output",
      "isManager": false,
      "position": { "x": 820, "y": 220 }
    },
    {
      "id": "chain-end",
      "type": "end",
      "label": "最终输出",
      "resultKey": "final_output",
      "position": { "x": 1080, "y": 240 }
    }
  ],
  "edges": [
    { "id": "e1", "from": "chain-start", "to": "chain-analysis" },
    { "id": "e2", "from": "chain-analysis", "to": "chain-worker" },
    { "id": "e3", "from": "chain-worker", "to": "chain-summary" },
    { "id": "e4", "from": "chain-summary", "to": "chain-end" }
  ],
  "execution": {
    "mode": "chain",
    "maxConcurrency": 1,
    "timeoutSec": 1800
  },
  "metadata": {
    "source": "template",
    "collaborationPattern": "prompt-chain",
    "warnings": []
  }
}
```

### 3. Agent 绑定

**方式**：设计时绑定。画布上点击节点 → 配置面板下拉选 Agent → `agentInstanceId` 回写到 DSL JSON。

**不采用运行时动态匹配**：需要 Agent 发现机制、能力描述、匹配算法，阶段 4 太重。

### 4. 画布节点类型

阶段 4 只暴露 3 种节点：

| type | 说明 | 约束 |
|---|---|---|
| `start` | 入口节点 | 不可删除、不可复制、只有一个 |
| `agent` | Agent 节点 | 可拖出、可配置（选 Agent + 填 inputTemplate）、可删除、有 input/output 端口 |
| `end` | 出口节点 | 不可删除、只有一个、收集上游输出 |

`condition` 节点阶段 4 不做。`kind`（worker/aggregator/orchestrator）不区分渲染外观，只影响 prompt 里的"协作身份：XX者"。

### 5. Orchestrator Agent

**职责**：阶段 4 为占位字段。它在执行中的作用仅限于 `inputTemplate` 里的 prompt 区分：

```
// kind='orchestrator', isManager=true
协作身份：编排者
期望输入：用户任务
期望输出：任务分派

// kind='worker'
协作身份：执行者
期望输入：用户任务
期望输出：处理结果

// kind='aggregator'
协作身份：汇总者
期望输入：执行结果
期望输出：最终结果
```

后续做条件分支、竞争、投票模式时，orchestrator 的角色再浮现。

### 6. NL→DSL 生成

**阶段 4 不做。** 画布页留一个"自然语言创建"按钮，标记"开发中"。

原因：DSL schema 复杂时 AI 无法可靠生成完整 JSON；需要模板库 + 校验重试等额外工程。

### 7. 上游输出注入规则（`{{upstream_outputs}}`）

**范围**：只看 edges 中**直连**到当前节点的上游节点，不含间接上游。

**格式**：结构化 Markdown，包含节点名标题 + 输出全文 + 交付物清单。

**示例**（"执行节点"收到的 `{{upstream_outputs}}` 展开）：

```markdown
## 分析节点
根据用户需求，任务可以拆解为以下三个步骤：
1. 收集目标市场的竞品数据
2. 分析差异化机会
3. 输出去重后的关键洞察

### Handoff files
- 分析节点 created research_plan.md
  - kind: workspace-file
  - path: /workspace/research_plan.md
  - size: 2048 bytes
```

**额外占位符**：`{{user_task}}` 独立于 `{{upstream_outputs}}`，展开为工作流最原始的用户输入。

**过滤**：只包含 activeEdges 中的边（条件分支场景下不走的边不注入，阶段 4 暂不涉及此逻辑）。

### 8. 节点消息组装

传给 Claude CLI 的 `-p` prompt 由三层拼接：

```
Layer 1: SOUL.md + IDENTITY.md + ...（Agent 角色定义）
Layer 2: inputTemplate（协作身份 + 期望输入/输出）
Layer 3: {{upstream_outputs}} + {{user_task}}（运行时数据）
```

### 9. 节点执行分发

按 `node.type` 走 if-else 分发：

| type | 行为 |
|---|---|
| `start` | `output = runtime.execution.task`（用户原始任务），瞬间完成，不 spawn 进程 |
| `end` | 收集直连上游输出，`execution.finalOutput = output`，不 spawn 进程 |
| `agent` | 调 RunnerManager 启动 Claude CLI 子进程，完成后收集 workspace 文件交付物 |

### 10. 执行引擎算法

**Kahn 算法动态执行版**（非一次性拓扑排序）：

```
completed = {}
running   = {}

while 还有未执行节点:
    ready = 所有"前置节点全部在 completed 里"的节点
    for node in ready[:maxConcurrency - len(running)]:
        running[node] = launch(node)
    await 任意一个完成
    completed[完成的节点] = 输出
    del running[完成的节点]
```

阶段 4 设置 `maxConcurrency=1`，行为退化为严格串行。后续改配置值即可支持并行，算法不变。

### 11. RunnerManager 改造

**改造前**：`dict[agent_key, process]` — 同一 Agent 的多次调用会互相覆盖。

**改造后**：`dict[(agent_key, run_id), process]` — 同一 Agent 可同时参与多个 workflow run。

### 12. 文件交接

**共享目录**：`workspaces/.runs/{run_id}/`，工作流启动时创建。所有节点的 Agent 进程通过 `--add-dir` 指向此目录。

**生命周期**：跑完保留不删，提供删除按钮让用户手动清理。

### 13. 执行反馈

**SSE 流**，事件类型：

| 事件 | 作用 |
|---|---|
| `workflow_started` | { runId, totalNodes } |
| `node_started` | { nodeId, type, agentKey? } |
| `node_completed` | { nodeId, output, files? } |
| `workflow_completed` | { runId, finalOutput } |
| `workflow_failed` | { runId, failedNodeId, error } |

前端只监听 `node_started` / `node_completed` 更新节点颜色（执行中=黄，完成=绿，失败=红）。

### 14. 执行状态

**内存存储**：`dict[workflow_run_id, WorkflowRunState]`，不持久化到数据库。跑完即丢（除非前端通过 SSE 接收了结果并展示）。

### 15. 失败处理

**立即终止**：任何节点失败，整个工作流标记失败，后续节点不执行。

后续可扩展 `maxRetries` 配置（阶段 4 不做）。

### 16. 数据存储

**新增表 `teams`**，团队与 workflow DSL 为 1:1 关系：

```sql
CREATE TABLE IF NOT EXISTS teams (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL DEFAULT 'admin',
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  dsl TEXT NOT NULL DEFAULT '{}',           -- DSL JSON 本体
  orchestrator_agent_id TEXT,               -- 占位，阶段 4 不做实际用途
  status TEXT NOT NULL DEFAULT 'draft',     -- draft | running | archived
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

画布编辑期间状态存前端内存，点"保存"按钮一次性 POST/PUT 到后端。

### 17. 路由设计

**页面路由**：

| 路由 | 模板 | 说明 |
|---|---|---|
| `GET /teams` | `teams/list.html` | 团队列表（替代 `/architectures/mine`） |
| `GET /teams/new` | `teams/canvas.html` | 创建新团队 → 跳转空白画布 |
| `GET /teams/{team_id}` | `teams/canvas.html` | 画布编辑器（Rete.js） |
| `GET /teams/{team_id}/run` | `teams/run.html` | 执行监控页 |

**API 路由**（`/api/teams`）：

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/teams` | 团队列表 |
| `POST` | `/api/teams` | 创建团队（含 DSL） |
| `GET` | `/api/teams/{team_id}` | 获取团队（含 DSL） |
| `PUT` | `/api/teams/{team_id}` | 更新 DSL |
| `DELETE` | `/api/teams/{team_id}` | 删除团队 |
| `POST` | `/api/teams/{team_id}/run` | 启动执行，返回 SSE 流 |
| `GET` | `/api/teams/{team_id}/runs` | 历史执行记录（预留，阶段 4 不做） |

### 18. 首屏加载

**Jinja2 注入**：DSL JSON 直接写入 `<script>` 标签：

```html
<script>
  window.__INITIAL_DSL__ = {{ dsl | tojson }};
</script>
```

Rete.js 初始化时读取此变量渲染画布，无额外 HTTP 请求，无首屏 loading。

### 19. 画布保存

**手动保存**：点"保存"按钮 → POST/PUT 到后端 → 一次写入 DB。

编辑期间所有操作（拖拽/连线/配置）只修改前端内存 + `window.__INITIAL_DSL__`，不自动同步后端。

### 20. 预置模板

阶段 4 只提供一个模板：**串行链**（prompt-chain）。

并行分发（broadcast）、条件分支（if-else）等模板预留在模板库里，但画布菜单上标记"开发中"。

---

## 阶段 4 产出

1. 团队列表页 + CRUD
2. 画布编辑器（Rete.js 3 节点类型：start / agent / end）
3. 串行链模板
4. 执行引擎（Kahn 动态就绪扫描，maxConcurrency=1）
5. SSE 执行反馈（node_started / node_completed → 节点变色）
6. 共享 worktree 文件交接
7. 代码结构：`app/teams/`（models.py / service.py / router.py / api.py）+ `app/static/js/canvas.js` + 对应模板

## 展期（后续阶段）

- NL→DSL 生成
- 条件分支（condition 节点）
- 并行执行（maxConcurrency > 1）
- 执行历史持久化
- 工作流失败重试
- DeepSeek 等多平台支持
