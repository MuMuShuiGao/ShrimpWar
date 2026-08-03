from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)


class TeamUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)
    dsl: str = Field(default="{}")


class TeamResponse(BaseModel):
    id: str
    name: str
    description: str
    dsl: str = "{}"
    orchestrator_agent_id: str = ""
    status: str = "draft"
    created_at: str
    updated_at: str


class RunRequest(BaseModel):
    task: str = Field(..., min_length=1)


class NodeState(BaseModel):
    node_id: str
    status: str  # pending | running | completed | failed
    output: str = ""
    error: str = ""


class RunStatus(BaseModel):
    run_id: str
    status: str  # running | completed | failed
    node_states: dict[str, NodeState] = {}
    final_output: str = ""
