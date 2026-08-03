import json
import uuid
from datetime import datetime, timezone

import aiosqlite

from app.teams.models import TeamCreate, TeamUpdate, TeamResponse

SERIAL_CHAIN_TEMPLATE = json.dumps({
    "schemaVersion": "1.0",
    "name": "",
    "description": "",
    "entryNodeId": "chain-start",
    "nodes": [
        {
            "id": "chain-start",
            "type": "start",
            "label": "用户输入",
            "outputKey": "user_task",
            "position": {"x": 60, "y": 240}
        },
        {
            "id": "chain-agent-1",
            "type": "agent",
            "label": "Agent 节点",
            "role": "",
            "kind": "worker",
            "agentInstanceId": None,
            "inputTemplate": "协作身份：执行者\n期望输入：用户任务\n期望输出：处理结果\n\n{{upstream_outputs}}",
            "outputKey": "agent_output",
            "isManager": False,
            "position": {"x": 300, "y": 220}
        },
        {
            "id": "chain-end",
            "type": "end",
            "label": "最终输出",
            "resultKey": "final_output",
            "position": {"x": 560, "y": 240}
        }
    ],
    "edges": [
        {"id": "e1", "from": "chain-start", "to": "chain-agent-1"},
        {"id": "e2", "from": "chain-agent-1", "to": "chain-end"}
    ],
    "execution": {
        "mode": "chain",
        "maxConcurrency": 1,
        "timeoutSec": 1800
    },
    "metadata": {
        "source": "template",
        "collaborationPattern": "prompt-chain",
        "warnings": []
    }
})


async def create_team(db: aiosqlite.Connection, payload: TeamCreate) -> TeamResponse:
    team_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    dsl_data = json.loads(SERIAL_CHAIN_TEMPLATE)
    dsl_data["name"] = payload.name
    dsl_data["description"] = payload.description

    await db.execute(
        """INSERT INTO teams (id, name, description, dsl, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (team_id, payload.name, payload.description, json.dumps(dsl_data, ensure_ascii=False), now, now),
    )
    await db.commit()
    return TeamResponse(
        id=team_id, name=payload.name, description=payload.description,
        dsl=json.dumps(dsl_data, ensure_ascii=False), created_at=now, updated_at=now,
    )


async def get_team(db: aiosqlite.Connection, team_id: str) -> TeamResponse | None:
    async with db.execute("SELECT * FROM teams WHERE id = ?", (team_id,)) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_response(row)


async def list_teams(db: aiosqlite.Connection) -> list[TeamResponse]:
    async with db.execute("SELECT * FROM teams ORDER BY created_at DESC") as cursor:
        rows = await cursor.fetchall()
        return [_row_to_response(row) for row in rows]


async def update_team(db: aiosqlite.Connection, team_id: str, payload: TeamUpdate) -> TeamResponse | None:
    team = await get_team(db, team_id)
    if team is None:
        return None

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dsl = payload.dsl
    try:
        dsl_data = json.loads(dsl)
        dsl_data["name"] = payload.name
        dsl_data["description"] = payload.description
        dsl = json.dumps(dsl_data, ensure_ascii=False)
    except json.JSONDecodeError:
        pass

    await db.execute(
        """UPDATE teams SET name = ?, description = ?, dsl = ?, updated_at = ? WHERE id = ?""",
        (payload.name, payload.description, dsl, now, team_id),
    )
    await db.commit()

    team.name = payload.name
    team.description = payload.description
    team.dsl = dsl
    team.updated_at = now
    return team


async def delete_team(db: aiosqlite.Connection, team_id: str) -> bool:
    team = await get_team(db, team_id)
    if team is None:
        return False
    await db.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    await db.commit()
    return True


def _row_to_response(row) -> TeamResponse:
    return TeamResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        dsl=row["dsl"],
        orchestrator_agent_id=row["orchestrator_agent_id"] or "",
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
