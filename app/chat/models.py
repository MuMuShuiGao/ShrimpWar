import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ConversationResponse(BaseModel):
    id: str
    agent_id: str
    title: str
    created_at: str = ""
    updated_at: str = ""


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str = ""
