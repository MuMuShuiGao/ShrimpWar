from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

from app.agents.models import AgentCreate, AgentUpdate
from app.agents.service import (
    create_agent,
    get_agent_by_key,
    list_agents,
    update_agent,
    update_agent_status,
)
from app.workspace.scaffold import read_file, read_config

router = APIRouter(tags=["agents-pages"])


@router.get("/agents")
async def page_list_agents(request: Request):
    agents = await list_agents(request.app.state.db)
    return request.app.state.templates.TemplateResponse(
        request, "agents/list.html", {"request": request, "agents": agents}
    )


@router.get("/agents/new")
async def page_create_agent(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "agents/create.html", {"request": request}
    )


@router.post("/agents")
async def handle_create_agent(request: Request):
    form = await request.form()
    payload = AgentCreate(
        agent_key=form.get("agent_key", ""),
        name=form.get("name", ""),
        description=form.get("description", ""),
    )
    db = request.app.state.db
    existing = await get_agent_by_key(db, payload.agent_key)
    if existing:
        return request.app.state.templates.TemplateResponse(
            request, "agents/create.html", {
                "request": request,
                "error": "Agent key 已被占用",
                "agent_key": payload.agent_key,
                "name": payload.name,
                "description": payload.description,
            },
            status_code=409,
        )
    agent = await create_agent(db, request.app.state.workspaces_root, payload)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/agents/{agent.agent_key}", status_code=303)


@router.get("/agents/{agent_key}")
async def page_detail_agent(request: Request, agent_key: str):
    return await _detail_context(request, agent_key)


@router.post("/agents/{agent_key}/edit")
async def handle_edit_agent(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    payload = AgentUpdate(
        name=form.get("name", agent.name),
        description=form.get("description", agent.description),
        model=form.get("model", "claude-sonnet-4-6"),
        temperature=float(form.get("temperature", 0.7)),
        maxTokens=int(form.get("maxTokens", 4096)),
        platform=form.get("platform", "claude-code"),
    )

    from app.workspace.scaffold import write_file
    workspace_path = _get_workspace_path(request, agent_key)

    file_fields = {
        "soul_content": "SOUL.md",
        "identity_content": "IDENTITY.md",
        "user_content": "USER.md",
        "agents_content": "AGENTS.md",
        "tools_content": "TOOLS.md",
    }
    for form_key, filename in file_fields.items():
        if form_key in form:
            write_file(workspace_path, filename, form.get(form_key, ""))

    await update_agent(request.app.state.db, agent_key, payload, workspace_path)

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/agents/{agent_key}", status_code=303)


@router.get("/agents/{agent_key}/status-fragment")
async def page_status_fragment(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)
    runner_status = request.app.state.runner.status(agent_key)
    display_status = runner_status if runner_status != "idle" else agent.status

    status_class = {
        "running": "bg-green-500/10 text-green-400",
        "error": "bg-red-500/10 text-red-400",
    }.get(display_status, "bg-zinc-800 text-zinc-500")

    dot_class = {
        "running": "bg-green-400 animate-pulse",
        "error": "bg-red-400",
    }.get(display_status, "bg-zinc-600")

    return request.app.state.templates.TemplateResponse(
        request, "components/status_badge.html", {
            "request": request,
            "status_class": status_class,
            "dot_class": dot_class,
            "display_status": display_status,
        }
    )


def _get_workspace_path(request: Request, agent_key: str) -> str:
    import os
    return os.path.join(request.app.state.workspaces_root, agent_key)


async def _detail_context(request: Request, agent_key: str, output: str = ""):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)
    workspace_path = _get_workspace_path(request, agent_key)

    runner_status = request.app.state.runner.status(agent_key)
    display_status = runner_status if runner_status != "idle" else agent.status

    return request.app.state.templates.TemplateResponse(
        request, "agents/detail.html", {
            "request": request,
            "agent": agent,
            "soul_content": read_file(workspace_path, "SOUL.md"),
            "identity_content": read_file(workspace_path, "IDENTITY.md"),
            "user_content": read_file(workspace_path, "USER.md"),
            "agents_content": read_file(workspace_path, "AGENTS.md"),
            "tools_content": read_file(workspace_path, "TOOLS.md"),
            "config": read_config(workspace_path),
            "output": output,
            "status_class": {
                "running": "bg-green-500/10 text-green-400",
                "error": "bg-red-500/10 text-red-400",
            }.get(display_status, "bg-zinc-800 text-zinc-500"),
            "dot_class": {
                "running": "bg-green-400 animate-pulse",
                "error": "bg-red-400",
            }.get(display_status, "bg-zinc-600"),
            "display_status": display_status,
        }
    )


@router.post("/agents/{agent_key}/run")
async def handle_run_agent(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    message = form.get("message", "").strip()
    if not message:
        return await _detail_context(request, agent_key)

    runner = request.app.state.runner
    if runner.is_running(agent_key):
        return await _detail_context(request, agent_key)

    await runner.start(agent_key, agent.workspace_path, message, agent.model)
    await update_agent_status(request.app.state.db, agent_key, "running")
    return RedirectResponse(url=f"/agents/{agent_key}", status_code=303)


@router.post("/agents/{agent_key}/stop")
async def handle_stop_agent(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    runner = request.app.state.runner
    proc = runner.get(agent_key)
    output = ""
    if proc:
        output = proc.last_error or proc.last_output
    await runner.stop(agent_key)
    await update_agent_status(request.app.state.db, agent_key, "idle")

    return await _detail_context(request, agent_key, output=output)
