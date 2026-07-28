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


async def start_claude_code(agent_process: AgentProcess, message: str, model: str = "") -> None:
    workspace_path = agent_process.workspace_path

    args = [
        "claude",
        "-p", message,
        f"--add-dir={workspace_path}",
        "--output-format=json",
        "--no-chrome",
    ]
    if model:
        args.extend(["--model", model])

    agent_process.status = "running"
    agent_process.started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    agent_process.last_output = ""
    agent_process.last_error = ""

    try:
        agent_process.process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await agent_process.process.communicate()

        agent_process.last_output = stdout.decode("utf-8", errors="replace").strip()
        agent_process.last_error = stderr.decode("utf-8", errors="replace").strip()

        if agent_process.process.returncode == 0:
            agent_process.status = "idle"
        else:
            agent_process.status = "error"

    except FileNotFoundError:
        agent_process.status = "error"
        agent_process.last_error = "Claude Code (claude) 命令未找到，请确认已安装 Claude CLI"
    except Exception as e:
        agent_process.status = "error"
        agent_process.last_error = str(e)

    agent_process.finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    agent_process.process = None
