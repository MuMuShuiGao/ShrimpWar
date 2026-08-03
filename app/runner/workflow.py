import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field

import aiosqlite


@dataclass
class NodeRunState:
    node_id: str
    node_type: str
    status: str = "pending"
    output: str = ""
    error: str = ""


@dataclass
class WorkflowRunState:
    run_id: str
    dsl: dict
    task: str
    node_states: dict[str, NodeRunState] = field(default_factory=dict)
    status: str = "running"
    final_output: str = ""
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class WorkflowEngine:
    def __init__(
        self,
        db: aiosqlite.Connection,
        runner_manager,
        workspaces_root: str,
    ):
        self.db = db
        self.runner = runner_manager
        self.workspaces_root = workspaces_root

    async def execute(self, dsl: dict, task: str):
        run_id = str(uuid.uuid4())
        nodes = dsl.get("nodes", [])
        edges = dsl.get("edges", [])
        execution = dsl.get("execution", {})
        max_concurrency = execution.get("maxConcurrency", 1)

        run_workspace = os.path.join(self.workspaces_root, ".runs", run_id)
        os.makedirs(run_workspace, exist_ok=True)

        state = WorkflowRunState(run_id=run_id, dsl=dsl, task=task)
        for node in nodes:
            state.node_states[node["id"]] = NodeRunState(
                node_id=node["id"], node_type=node.get("type", "agent")
            )

        yield self._sse("workflow_started", {"runId": run_id, "totalNodes": len(nodes)})

        completed: dict[str, str] = {}
        running: dict[str, asyncio.Task] = {}

        while True:
            ready = _ready_nodes(nodes, edges, completed, running, state.node_states)
            if not ready and not running:
                break

            for node in ready[:max_concurrency]:
                task_obj = asyncio.create_task(
                    self._run_node(node, state, completed, run_workspace)
                )
                running[node["id"]] = task_obj

            if not running:
                break

            # Poll frequently to drain events while waiting for task completion
            while running:
                done, _ = await asyncio.wait(
                    running.values(), return_when=asyncio.FIRST_COMPLETED, timeout=0.25
                )

                # Drain pending events immediately
                while not state.event_queue.empty():
                    yield state.event_queue.get_nowait()

                if done:
                    break

            for finished in done:
                node_id = None
                for nid, t in list(running.items()):
                    if t is finished:
                        node_id = nid
                        break
                if node_id:
                    del running[node_id]
                    ns = state.node_states[node_id]

                    event_type = "node_completed" if ns.status == "completed" else "node_failed"
                    yield self._sse(event_type, {
                        "nodeId": node_id,
                        "status": ns.status,
                        "output": ns.output[:500] if ns.output else "",
                        "error": ns.error,
                    })
                    if ns.status == "completed":
                        completed[node_id] = ns.output
                    else:
                        state.status = "failed"
                        for t in running.values():
                            t.cancel()
                        yield self._sse("workflow_failed", {
                            "runId": run_id,
                            "failedNodeId": node_id,
                            "error": ns.error,
                        })
                        return

        state.status = "completed"
        state.final_output = completed.get(_find_end_node_id(nodes), "")
        yield self._sse("workflow_completed", {
            "runId": run_id,
            "finalOutput": state.final_output[:2000],
        })

    async def _run_node(
        self,
        node: dict,
        state: WorkflowRunState,
        completed: dict[str, str],
        run_workspace: str,
    ) -> None:
        node_id = node["id"]
        ns = state.node_states[node_id]
        ns.status = "running"

        await state.event_queue.put(
            self._sse("node_started", {
                "nodeId": node_id,
                "type": node.get("type", "agent"),
                "label": node.get("label", ""),
            })
        )

        try:
            node_type = node.get("type", "agent")
            if node_type == "start":
                ns.output = state.task
                ns.status = "completed"
            elif node_type == "end":
                upstream = _collect_upstream(node_id, state.dsl.get("edges", []), completed)
                ns.output = "\n\n".join(upstream.values()) if upstream else ""
                ns.status = "completed"
            elif node_type == "agent":
                await self._execute_agent(node, state, completed, run_workspace, ns)
            else:
                ns.output = ""
                ns.status = "completed"
        except Exception as e:
            ns.status = "failed"
            ns.error = str(e)

    async def _execute_agent(
        self,
        node: dict,
        state: WorkflowRunState,
        completed: dict[str, str],
        run_workspace: str,
        ns: NodeRunState,
    ) -> None:
        agent_instance_id = node.get("agentInstanceId")
        if not agent_instance_id:
            ns.status = "failed"
            ns.error = f"节点 '{node.get('label', node['id'])}' 未绑定 Agent，请点击节点选择 Agent"
            return

        # Resolve agent_instance_id to agent_key
        agent_key = agent_instance_id
        agent_row = await _get_agent_by_id(self.db, agent_instance_id)
        if agent_row:
            agent_key = agent_row["agent_key"]
        else:
            # Try by agent_key directly
            agent_row = await _get_agent_by_key(self.db, agent_instance_id)
            if not agent_row:
                ns.status = "failed"
                ns.error = f"Agent '{agent_instance_id}' 不存在"
                return

        prompt = _build_agent_prompt(node, state, completed)
        prompt = _prepend_agent_soul(self.workspaces_root, agent_key, prompt)

        model = ""
        config = _read_agent_config(self.workspaces_root, agent_key)
        if config:
            model = config.get("model", "")

        try:
            run_key_id = f"{state.run_id}:{node['id']}"
            proc = self.runner.get_or_create(agent_key, run_key_id, run_workspace)
            if proc.status == "running":
                ns.status = "failed"
                ns.error = f"Agent {agent_key} 正在运行中"
                return

            proc.workspace_path = run_workspace

            await self.runner.start(
                agent_key=agent_key,
                workspace_path=run_workspace,
                message=prompt,
                model=model,
                run_id=run_key_id,
            )

            while proc.status == "running":
                await asyncio.sleep(0.5)

            if proc.status == "idle":
                ns.output = proc.last_output
                ns.status = "completed"

                files = _collect_files(run_workspace)
                if files:
                    file_list = "\n".join(
                        f"- {f['name']}\n  - kind: workspace-file\n  - path: {f['path']}\n  - size: {f['size']} bytes"
                        for f in files
                    )
                    ns.output = ns.output + f"\n\n### Handoff files\n{file_list}"
            else:
                ns.status = "failed"
                ns.error = proc.last_error or "Agent 执行失败"

        except Exception as e:
            ns.status = "failed"
            ns.error = str(e)

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# --- Helper functions ---

def _ready_nodes(nodes, edges, completed, running, node_states):
    ready = []
    for node in nodes:
        nid = node["id"]
        if nid in completed or nid in running:
            continue
        ns = node_states.get(nid)
        if ns and ns.status == "failed":
            continue
        upstream_ids = [e["from"] for e in edges if e["to"] == nid]
        if all(uid in completed for uid in upstream_ids):
            ready.append(node)
    return ready


def _collect_upstream(node_id, edges, completed):
    upstream = {}
    for e in edges:
        if e["to"] == node_id and e["from"] in completed:
            upstream[e["from"]] = completed[e["from"]]
    return upstream


def _build_agent_prompt(node, state, completed):
    input_template = node.get(
        "inputTemplate",
        "协作身份：执行者\n期望输入：用户任务\n期望输出：处理结果\n\n{{upstream_outputs}}",
    )

    upstream = _collect_upstream(node["id"], state.dsl.get("edges", []), completed)
    upstream_md = ""
    for nid, output in upstream.items():
        label = _node_label(state.dsl.get("nodes", []), nid)
        upstream_md += f"## {label}\n{output}\n\n"

    prompt = input_template.replace("{{upstream_outputs}}", upstream_md.strip())
    prompt = prompt.replace("{{user_task}}", state.task)

    return prompt


def _node_label(nodes, node_id):
    for n in nodes:
        if n["id"] == node_id:
            return n.get("label", node_id)
    return node_id


def _find_end_node_id(nodes):
    for n in nodes:
        if n.get("type") == "end":
            return n["id"]
    return ""


def _collect_files(workspace_path):
    files = []
    if not os.path.exists(workspace_path):
        return files
    for name in os.listdir(workspace_path):
        fp = os.path.join(workspace_path, name)
        if os.path.isfile(fp):
            size = os.path.getsize(fp)
            files.append({"name": name, "path": f"/workspace/{name}", "size": size})
    return files


def _prepend_agent_soul(workspaces_root, agent_key, prompt):
    from app.workspace.scaffold import read_file
    agent_ws = os.path.join(workspaces_root, agent_key)
    if not os.path.exists(agent_ws):
        return prompt
    soul = read_file(agent_ws, "SOUL.md").strip()
    identity = read_file(agent_ws, "IDENTITY.md").strip()
    parts = []
    if soul:
        parts.append(soul)
    if identity:
        parts.append(identity)
    if parts:
        return "\n\n".join(parts) + "\n\n---\n\n" + prompt
    return prompt


def _read_agent_config(workspaces_root, agent_key):
    from app.workspace.scaffold import read_config
    agent_ws = os.path.join(workspaces_root, agent_key)
    if not os.path.exists(agent_ws):
        return None
    return read_config(agent_ws)


async def _get_agent_by_id(db: aiosqlite.Connection, agent_id: str):
    async with db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def _get_agent_by_key(db: aiosqlite.Connection, agent_key: str):
    async with db.execute("SELECT * FROM agents WHERE agent_key = ?", (agent_key,)) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)
