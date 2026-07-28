import json
import os
import uuid
from datetime import datetime, timezone

import aiosqlite

from app.agents.models import AgentCreate, AgentUpdate, AgentResponse
from app.workspace.scaffold import scaffold, read_file, write_file, read_config, write_config


async def create_agent(
    db: aiosqlite.Connection,
    workspaces_root: str,
    payload: AgentCreate,
) -> AgentResponse:
    agent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    workspace_path = scaffold(
        workspace_root=workspaces_root,
        agent_key=payload.agent_key,
        name=payload.name,
        description=payload.description,
        agent_id=agent_id,
    )

    await db.execute(
        """INSERT INTO agents (id, name, description, agent_key, workspace_path, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (agent_id, payload.name, payload.description, payload.agent_key, workspace_path, now, now),
    )
    await db.commit()

    return AgentResponse(
        id=agent_id,
        name=payload.name,
        description=payload.description,
        agent_key=payload.agent_key,
        avatar="",
        status="idle",
        created_at=now,
        updated_at=now,
    )


async def get_agent_by_key(db: aiosqlite.Connection, agent_key: str) -> AgentResponse | None:
    async with db.execute("SELECT * FROM agents WHERE agent_key = ?", (agent_key,)) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_response(row)


async def list_agents(db: aiosqlite.Connection) -> list[AgentResponse]:
    async with db.execute("SELECT * FROM agents ORDER BY created_at DESC") as cursor:
        rows = await cursor.fetchall()
        return [_row_to_response(row) for row in rows]


async def update_agent(
    db: aiosqlite.Connection,
    agent_key: str,
    payload: AgentUpdate,
    workspace_path: str,
) -> AgentResponse | None:
    agent = await get_agent_by_key(db, agent_key)
    if agent is None:
        return None

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute(
        """UPDATE agents SET name = ?, description = ?, updated_at = ? WHERE agent_key = ?""",
        (payload.name, payload.description, now, agent_key),
    )
    await db.commit()

    config = read_config(workspace_path)
    config["name"] = payload.name
    config["description"] = payload.description
    config["model"] = payload.model
    config["temperature"] = payload.temperature
    config["maxTokens"] = payload.maxTokens
    config["platform"] = payload.platform
    write_config(workspace_path, config)

    agent.name = payload.name
    agent.description = payload.description
    agent.updated_at = now
    agent.model = payload.model
    agent.temperature = payload.temperature
    agent.maxTokens = payload.maxTokens
    agent.platform = payload.platform
    return agent


async def update_agent_status(
    db: aiosqlite.Connection,
    agent_key: str,
    status: str,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute(
        "UPDATE agents SET status = ?, updated_at = ? WHERE agent_key = ?",
        (status, now, agent_key),
    )
    await db.commit()


def _row_to_response(row) -> AgentResponse:
    return AgentResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        agent_key=row["agent_key"],
        avatar=row["avatar"],
        status=row["status"],
        workspace_path=row["workspace_path"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
