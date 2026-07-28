import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    agent_key: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)


class AgentUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)
    model: str = Field(default="claude-sonnet-4-6")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    maxTokens: int = Field(default=4096, ge=1, le=200000)
    platform: str = Field(default="claude-code")


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    agent_key: str
    avatar: str
    status: str
    workspace_path: str = ""
    created_at: str = ""
    updated_at: str = ""

    model: str = ""
    temperature: float = 0.7
    maxTokens: int = 4096
    platform: str = "claude-code"


class StatusResponse(BaseModel):
    status: str
    agent_key: str


class RunRequest(BaseModel):
    message: str = Field(..., min_length=1)
