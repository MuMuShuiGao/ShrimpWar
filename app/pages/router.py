from fastapi import APIRouter, Request

from app.agents.service import list_agents

router = APIRouter(tags=["pages"])


@router.get("/")
async def page_home(request: Request):
    agents = await list_agents(request.app.state.db)
    agent_count = len(agents)
    return request.app.state.templates.TemplateResponse(
        request, "pages/home.html", {
            "request": request,
            "active_page": "/",
            "agent_count": agent_count,
        }
    )


@router.get("/my-den")
async def page_my_den(request: Request):
    agents = await list_agents(request.app.state.db)
    configured = sum(1 for a in agents if a.status == "idle")
    unconfigured = len(agents) - configured
    return request.app.state.templates.TemplateResponse(
        request, "pages/my_den.html", {
            "request": request,
            "active_page": "/my-den",
            "agents": agents,
            "total": len(agents),
            "configured": configured,
            "unconfigured": unconfigured,
        }
    )


@router.get("/architectures/mine")
async def page_architectures(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "pages/architectures.html", {
            "request": request,
            "active_page": "/architectures/mine",
        }
    )


@router.get("/market")
async def page_market(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "pages/market.html", {
            "request": request,
            "active_page": "/market",
        }
    )


@router.get("/settings/providers")
async def page_settings_providers(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "pages/settings_providers.html", {
            "request": request,
            "active_page": "/settings/providers",
        }
    )
