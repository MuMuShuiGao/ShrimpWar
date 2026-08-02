import asyncio
import json

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.service import get_agent_by_key
from app.chat.models import ConversationResponse, MessageResponse
from app.chat.service import (
    create_conversation,
    get_conversation,
    list_conversations,
    delete_conversation,
    add_message,
    list_messages,
    get_recent_messages,
    update_conversation_title,
)


router = APIRouter(prefix="/agents/{agent_key}", tags=["chat-api"])


@router.get("/conversations", response_model=list[ConversationResponse])
async def api_list_conversations(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)
    return await list_conversations(request.app.state.db, agent.id)


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def api_create_conversation(request: Request, agent_key: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)
    return await create_conversation(request.app.state.db, agent.id)


@router.delete("/conversations/{conv_id}")
async def api_delete_conversation(request: Request, agent_key: str, conv_id: str):
    conv = await get_conversation(request.app.state.db, conv_id)
    if conv is None:
        raise HTTPException(status_code=404)
    await delete_conversation(request.app.state.db, conv_id)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def api_list_messages(request: Request, agent_key: str, conv_id: str):
    conv = await get_conversation(request.app.state.db, conv_id)
    if conv is None:
        raise HTTPException(status_code=404)
    return await list_messages(request.app.state.db, conv_id)


@router.post("/conversations/{conv_id}/send")
async def api_send_message(request: Request, agent_key: str, conv_id: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    conv = await get_conversation(request.app.state.db, conv_id)
    if conv is None:
        raise HTTPException(status_code=404)

    runner = request.app.state.runner
    if runner.is_running(agent_key):
        raise HTTPException(status_code=409, detail="Agent 正在运行中")

    form = await request.form()
    message = form.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    await add_message(request.app.state.db, conv_id, "user", message)

    messages = await list_messages(request.app.state.db, conv_id)
    if len(messages) == 1:
        title = message[:30]
        await update_conversation_title(request.app.state.db, conv_id, title)

    context_msgs = await get_recent_messages(request.app.state.db, conv_id, rounds=10)
    context_dicts = [{"role": m.role, "content": m.content} for m in context_msgs[:-1]]

    queue: asyncio.Queue = asyncio.Queue()
    await runner.start(
        agent_key=agent_key,
        workspace_path=agent.workspace_path,
        message=message,
        model=agent.model,
        queue=queue,
        context_messages=context_dicts if context_dicts else None,
    )

    return {"status": "ok"}


@router.get("/conversations/{conv_id}/stream")
async def api_stream(request: Request, agent_key: str, conv_id: str):
    agent = await get_agent_by_key(request.app.state.db, agent_key)
    if agent is None:
        raise HTTPException(status_code=404)

    runner = request.app.state.runner
    proc = runner.get(agent_key)
    if proc is None or proc.queue is None:
        raise HTTPException(status_code=404, detail="没有正在进行的流")

    queue = proc.queue

    async def event_generator():
        full_content = ""
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                full_content += chunk
                yield f"event: token\ndata: {_sse_encode(chunk)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if full_content:
                await add_message(request.app.state.db, conv_id, "assistant", full_content)
            yield f"event: done\ndata: {json.dumps({'status': proc.status})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_encode(text: str) -> str:
    return text.replace("\n", "\ndata: ")
