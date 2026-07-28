import os
from fastapi import APIRouter, Request, HTTPException

from app.agents.models import AgentCreate, AgentUpdate, AgentResponse, StatusResponse, RunRequest
from app.agents.service import (
    create_agent,
    get_agent_by_key,
    list_agents,
    update_agent,
    update_agent_status,
)

router = APIRouter(prefix="/api/agents", tags=["agents-api"])


@router.get("", response_model=list[AgentResponse])
async def api_list_agents(request: Request):
    return await list_agents(request.app.state.db)


@router.post("", response_model=AgentResponse, status_code=201)
async def api_create_agent(request: Request, payload: AgentCreate):
    db = request.app.state.db
    existing = await get_agent_by_key(db, payload.agent_key)
    if existing:
        raise HTTPException(status_code=409, detail="Agent key 已被占用")
    return await create_agent(db, request.app.state.workspaces_root, payload)


@router.get("/{agent_key}", response_model=AgentResponse)
async def api_get_agent(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)
    return agent


@router.put("/{agent_key}", response_model=AgentResponse)
async def api_update_agent(request: Request, agent_key: str, payload: AgentUpdate):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)
    workspace_path = os.path.join(request.app.state.workspaces_root, agent_key)
    result = await update_agent(request.app.state.db, agent_key, payload, workspace_path)
    return result


@router.get("/{agent_key}/status", response_model=StatusResponse)
async def api_agent_status(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)
    runner_status = request.app.state.runner.status(agent_key)
    if runner_status != "idle":
        return StatusResponse(status=runner_status, agent_key=agent_key)
    return StatusResponse(status=agent.status, agent_key=agent_key)


@router.post("/{agent_key}/run")
async def api_run_agent(request: Request, agent_key: str, payload: RunRequest):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    runner = request.app.state.runner
    if runner.is_running(agent_key):
        raise HTTPException(status_code=409, detail="Agent 正在运行中")

    await runner.start(agent_key, agent.workspace_path, payload.message, agent.model)
    await update_agent_status(request.app.state.db, agent_key, "running")
    return {"status": "running", "agent_key": agent_key}


@router.post("/{agent_key}/stop")
async def api_stop_agent(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    runner = request.app.state.runner
    await runner.stop(agent_key)
    await update_agent_status(request.app.state.db, agent_key, "idle")
    return {"status": "idle", "agent_key": agent_key}
