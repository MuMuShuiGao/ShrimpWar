import asyncio
from collections.abc import Callable, Awaitable

from app.runner.process import AgentProcess, start_claude_code


OnComplete = Callable[[str, str], Awaitable[None]]


class RunnerManager:
    def __init__(self, on_complete: OnComplete | None = None):
        self._processes: dict[str, AgentProcess] = {}
        self._on_complete = on_complete

    @staticmethod
    def _make_key(agent_key: str, run_id: str) -> str:
        return f"{agent_key}:{run_id}"

    def get(self, agent_key: str, run_id: str = "") -> AgentProcess | None:
        if run_id:
            return self._processes.get(self._make_key(agent_key, run_id))
        for key, proc in self._processes.items():
            if key.startswith(f"{agent_key}:"):
                return proc
        return None

    def get_or_create(self, agent_key: str, run_id: str, workspace_path: str) -> AgentProcess:
        key = self._make_key(agent_key, run_id)
        if key not in self._processes:
            self._processes[key] = AgentProcess(
                agent_key=agent_key,
                workspace_path=workspace_path,
            )
        return self._processes[key]

    def status(self, agent_key: str, run_id: str = "") -> str:
        if run_id:
            proc = self._processes.get(self._make_key(agent_key, run_id))
            if proc is None:
                return "idle"
            return proc.status
        for key, proc in self._processes.items():
            if key.startswith(f"{agent_key}:") and proc.status != "idle":
                return proc.status
        return "idle"

    def is_running(self, agent_key: str, run_id: str = "") -> bool:
        if run_id:
            proc = self._processes.get(self._make_key(agent_key, run_id))
            return proc is not None and proc.status == "running"
        for key, proc in self._processes.items():
            if key.startswith(f"{agent_key}:") and proc.status == "running":
                return True
        return False

    async def start(
        self,
        agent_key: str,
        workspace_path: str,
        message: str,
        model: str = "",
        queue: asyncio.Queue | None = None,
        context_messages: list[dict[str, str]] | None = None,
        run_id: str = "",
    ) -> AgentProcess:
        if not run_id:
            run_id = "default"
        proc = self.get_or_create(agent_key, run_id, workspace_path)

        if proc.status == "running":
            raise RuntimeError(f"Agent {agent_key} 正在运行中")

        proc.workspace_path = workspace_path
        proc.queue = queue

        asyncio.create_task(self._run_and_callback(proc, message, model, context_messages))

        return proc

    async def _run_and_callback(
        self,
        proc: AgentProcess,
        message: str,
        model: str,
        context_messages: list[dict[str, str]] | None = None,
    ) -> None:
        await start_claude_code(proc, message, model, context_messages)
        if self._on_complete:
            await self._on_complete(proc.agent_key, proc.status)

    async def stop(self, agent_key: str, run_id: str = "") -> None:
        if run_id:
            proc = self._processes.pop(self._make_key(agent_key, run_id), None)
            if proc is None:
                return
            await self._stop_proc(proc)
        else:
            to_stop = [
                (k, p) for k, p in self._processes.items()
                if k.startswith(f"{agent_key}:")
            ]
            for k, p in to_stop:
                del self._processes[k]
                await self._stop_proc(p)

    async def _stop_proc(self, proc: AgentProcess) -> None:
        if proc.process is None:
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
        if proc.queue is not None:
            await proc.queue.put(None)
            proc.queue = None
        proc.status = "idle"
        proc.process = None
