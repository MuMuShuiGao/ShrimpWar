import json

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from app.teams.models import TeamCreate, TeamUpdate, TeamResponse, RunRequest
from app.teams.service import (
    create_team,
    get_team,
    list_teams,
    update_team,
    delete_team,
)


router = APIRouter(prefix="/teams", tags=["teams-api"])


@router.get("", response_model=list[TeamResponse])
async def api_list_teams(request: Request):
    return await list_teams(request.app.state.db)


@router.post("", response_model=TeamResponse, status_code=201)
async def api_create_team(request: Request, payload: TeamCreate):
    return await create_team(request.app.state.db, payload)


@router.get("/{team_id}", response_model=TeamResponse)
async def api_get_team(request: Request, team_id: str):
    team = await get_team(request.app.state.db, team_id)
    if team is None:
        raise HTTPException(status_code=404)
    return team


@router.put("/{team_id}", response_model=TeamResponse)
async def api_update_team(request: Request, team_id: str, payload: TeamUpdate):
    result = await update_team(request.app.state.db, team_id, payload)
    if result is None:
        raise HTTPException(status_code=404)
    return result


@router.delete("/{team_id}", status_code=204)
async def api_delete_team(request: Request, team_id: str):
    deleted = await delete_team(request.app.state.db, team_id)
    if not deleted:
        raise HTTPException(status_code=404)


@router.post("/{team_id}/run")
async def api_run_team(request: Request, team_id: str, payload: RunRequest):
    team = await get_team(request.app.state.db, team_id)
    if team is None:
        raise HTTPException(status_code=404)

    try:
        dsl = json.loads(team.dsl)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="DSL 格式无效")

    # Validate DAG structure
    nodes = dsl.get("nodes", [])
    edges = dsl.get("edges", [])
    node_ids = {n["id"] for n in nodes}
    for e in edges:
        if e["from"] not in node_ids or e["to"] not in node_ids:
            raise HTTPException(
                status_code=400,
                detail=f"边引用了不存在的节点: {e.get('from')} -> {e.get('to')}",
            )
    if not any(n.get("type") == "start" for n in nodes):
        raise HTTPException(status_code=400, detail="DSL 缺少 start 节点")
    if not any(n.get("type") == "end" for n in nodes):
        raise HTTPException(status_code=400, detail="DSL 缺少 end 节点")

    from app.runner.workflow import WorkflowEngine
    engine = WorkflowEngine(
        request.app.state.db,
        request.app.state.runner,
        request.app.state.workspaces_root,
    )

    async def event_generator():
        async for sse_msg in engine.execute(dsl, payload.task):
            yield sse_msg

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
