import asyncio
import os
from collections.abc import Callable, Awaitable

from app.runner.process import AgentProcess, start_claude_code


OnComplete = Callable[[str, str], Awaitable[None]]


class RunnerManager:
    def __init__(self, on_complete: OnComplete | None = None):
        self._processes: dict[str, AgentProcess] = {}
        self._on_complete = on_complete
    def get(self, agent_key: str) -> AgentProcess | None:
        return self._processes.get(agent_key)

    def get_or_create(self, agent_key: str, workspace_path: str) -> AgentProcess:
        if agent_key not in self._processes:
            self._processes[agent_key] = AgentProcess(
                agent_key=agent_key,
                workspace_path=workspace_path,
            )
        return self._processes[agent_key]

    def status(self, agent_key: str) -> str:
        proc = self._processes.get(agent_key)
        if proc is None:
            return "idle"
        return proc.status

    def is_running(self, agent_key: str) -> bool:
        proc = self._processes.get(agent_key)
        if proc is None:
            return False
        return proc.status == "running"

    async def start(self, agent_key: str, workspace_path: str, message: str, model: str = "") -> AgentProcess:
        proc = self.get_or_create(agent_key, workspace_path)

        if proc.status == "running":
            raise RuntimeError(f"Agent {agent_key} 正在运行中")

        proc.workspace_path = workspace_path

        asyncio.create_task(self._run_and_callback(proc, message, model))

        return proc

    async def _run_and_callback(self, proc: AgentProcess, message: str, model: str) -> None:
        await start_claude_code(proc, message, model)
        if self._on_complete:
            await self._on_complete(proc.agent_key, proc.status)

    async def stop(self, agent_key: str) -> None:
        proc = self._processes.get(agent_key)
        if proc is None or proc.process is None:
            return

        try:
            proc.process.terminate()
            try:
                await asyncio.wait_for(proc.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.process.kill()
                await proc.process.wait()
        except ProcessLookupError:
            pass

        proc.status = "idle"
        proc.process = None
