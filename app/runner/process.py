import asyncio
import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AgentProcess:
    agent_key: str
    workspace_path: str
    process: asyncio.subprocess.Process | None = None
    status: str = "idle"
    started_at: str | None = None
    finished_at: str | None = None
    last_output: str = ""
    last_error: str = ""
    queue: asyncio.Queue | None = None


async def start_claude_code(
    agent_process: AgentProcess,
    message: str,
    model: str = "",
    context_messages: list[dict[str, str]] | None = None,
) -> None:
    workspace_path = agent_process.workspace_path
    queue = agent_process.queue

    if context_messages:
        context_lines = ["以下为最近对话记录：", ""]
        for msg in context_messages:
            role_label = "用户" if msg["role"] == "user" else "助手"
            context_lines.append(f"{role_label}: {msg['content']}")
            context_lines.append("")
        context_lines.append(f"用户: {message}")
        full_message = "\n".join(context_lines)
    else:
        full_message = message

    args = [
        "claude",
        "-p", full_message,
        f"--add-dir={workspace_path}",
        "--no-chrome",
    ]
    if model:
        args.extend(["--model", model])

    agent_process.status = "running"
    agent_process.started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    agent_process.last_output = ""

    try:
        agent_process.process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if queue is not None:
            await _stream_stdout(agent_process, queue)
        else:
            await _read_all(agent_process)

    except FileNotFoundError:
        agent_process.status = "error"
        agent_process.last_error = "Claude Code (claude) 命令未找到，请确认已安装 Claude CLI"
        if queue is not None:
            await queue.put(None)
    except Exception as e:
        agent_process.status = "error"
        agent_process.last_error = str(e)
        if queue is not None:
            await queue.put(None)

    agent_process.finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    agent_process.process = None


async def _read_all(agent_process: AgentProcess) -> None:
    stdout, stderr = await agent_process.process.communicate()
    agent_process.last_output = stdout.decode("utf-8", errors="replace").strip()
    agent_process.last_error = stderr.decode("utf-8", errors="replace").strip()
    agent_process.status = "idle" if agent_process.process.returncode == 0 else "error"


async def _stream_stdout(agent_process: AgentProcess, queue: asyncio.Queue) -> None:
    full_output = ""
    full_error = ""

    async def _read_stderr() -> None:
        nonlocal full_error
        if agent_process.process.stderr:
            err = await agent_process.process.stderr.read()
            if err:
                full_error = err.decode("utf-8", errors="replace").strip()

    import asyncio as _asyncio
    stderr_task = _asyncio.create_task(_read_stderr())

    if agent_process.process.stdout:
        async for line in agent_process.process.stdout:
            text = line.decode("utf-8", errors="replace")
            full_output += text
            await queue.put(text)

    await agent_process.process.wait()
    await stderr_task

    agent_process.last_output = full_output.strip()
    agent_process.last_error = full_error
    agent_process.status = "idle" if agent_process.process.returncode == 0 else "error"
    await queue.put(None)
