import json

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

from app.teams.models import TeamCreate, TeamUpdate
from app.teams.service import (
    create_team,
    get_team,
    list_teams,
    update_team,
    delete_team,
)
from app.agents.service import list_agents

router = APIRouter(tags=["teams-pages"])


@router.get("/teams")
async def page_list_teams(request: Request):
    teams = await list_teams(request.app.state.db)
    return request.app.state.templates.TemplateResponse(
        request, "teams/list.html", {
            "request": request,
            "active_page": "/teams",
            "teams": teams,
            "total": len(teams),
        }
    )


@router.get("/teams/new")
async def page_new_team(request: Request):
    agents = await list_agents(request.app.state.db)
    return request.app.state.templates.TemplateResponse(
        request, "teams/canvas.html", {
            "request": request,
            "active_page": "/teams",
            "team": None,
            "is_new": True,
            "agents": agents,
        }
    )


@router.get("/teams/{team_id}")
async def page_edit_team(request: Request, team_id: str):
    team = await get_team(request.app.state.db, team_id)
    if team is None:
        raise HTTPException(status_code=404)
    agents = await list_agents(request.app.state.db)
    return request.app.state.templates.TemplateResponse(
        request, "teams/canvas.html", {
            "request": request,
            "active_page": "/teams",
            "team": team,
            "is_new": False,
            "agents": agents,
        }
    )


@router.get("/teams/{team_id}/run")
async def page_run_team(request: Request, team_id: str):
    team = await get_team(request.app.state.db, team_id)
    if team is None:
        raise HTTPException(status_code=404)
    return request.app.state.templates.TemplateResponse(
        request, "teams/run.html", {
            "request": request,
            "active_page": "/teams",
            "team": team,
        }
    )


@router.post("/teams")
async def handle_create_team(request: Request):
    form = await request.form()
    payload = TeamCreate(
        name=form.get("name", "新团队"),
        description=form.get("description", ""),
    )
    team = await create_team(request.app.state.db, payload)
    return RedirectResponse(url=f"/teams/{team.id}", status_code=303)


@router.post("/teams/{team_id}/delete")
async def handle_delete_team(request: Request, team_id: str):
    deleted = await delete_team(request.app.state.db, team_id)
    if not deleted:
        raise HTTPException(status_code=404)
    return RedirectResponse(url="/teams", status_code=303)
