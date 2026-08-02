from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

from app.agents.service import get_agent_by_key
from app.chat.service import (
    create_conversation,
    get_conversation,
    list_conversations,
    delete_conversation,
    list_messages,
)


router = APIRouter(tags=["chat-pages"])


@router.get("/agents/{agent_key}/chat")
async def page_chat(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    conversations = await list_conversations(request.app.state.db, agent.id)
    if conversations:
        return RedirectResponse(url=f"/agents/{agent_key}/chat/{conversations[0].id}", status_code=303)
    return await _render_chat(request, agent, conversations, None, [])


@router.get("/agents/{agent_key}/chat/new")
async def page_new_chat(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    conv = await create_conversation(request.app.state.db, agent.id)
    return RedirectResponse(url=f"/agents/{agent_key}/chat/{conv.id}", status_code=303)


@router.post("/agents/{agent_key}/chat/{conv_id}/delete")
async def handle_delete_chat(request: Request, agent_key: str, conv_id: str):
    conv = await get_conversation(request.app.state.db, conv_id)
    if conv is None:
        raise HTTPException(status_code=404)

    await delete_conversation(request.app.state.db, conv_id)
    return RedirectResponse(url=f"/agents/{agent_key}/chat", status_code=303)


@router.get("/agents/{agent_key}/chat/{conv_id}")
async def page_chat_conv(request: Request, agent_key: str, conv_id: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    conv = await get_conversation(request.app.state.db, conv_id)
    if conv is None:
        raise HTTPException(status_code=404)

    conversations = await list_conversations(request.app.state.db, agent.id)
    messages = await list_messages(request.app.state.db, conv_id)
    return await _render_chat(request, agent, conversations, conv, messages)


async def _render_chat(request, agent, conversations, current_conv, messages):
    return request.app.state.templates.TemplateResponse(
        request, "agents/chat.html", {
            "request": request,
            "agent": agent,
            "conversations": conversations,
            "current_conv": current_conv,
            "messages": messages,
        }
    )
