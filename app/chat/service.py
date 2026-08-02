import uuid
from datetime import datetime, timezone

import aiosqlite

from app.chat.models import ConversationResponse, MessageResponse


async def create_conversation(db: aiosqlite.Connection, agent_id: str) -> ConversationResponse:
    conv_id = str(uuid.uuid4())
    now = _now()
    await db.execute(
        "INSERT INTO conversations (id, agent_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, agent_id, "新对话", now, now),
    )
    await db.commit()
    return ConversationResponse(id=conv_id, agent_id=agent_id, title="新对话", created_at=now, updated_at=now)


async def get_conversation(db: aiosqlite.Connection, conv_id: str) -> ConversationResponse | None:
    async with db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return _conv_row_to_response(row)


async def list_conversations(db: aiosqlite.Connection, agent_id: str) -> list[ConversationResponse]:
    async with db.execute(
        "SELECT * FROM conversations WHERE agent_id = ? ORDER BY updated_at DESC", (agent_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [_conv_row_to_response(row) for row in rows]


async def delete_conversation(db: aiosqlite.Connection, conv_id: str) -> None:
    await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    await db.commit()


async def add_message(db: aiosqlite.Connection, conv_id: str, role: str, content: str) -> MessageResponse:
    msg_id = str(uuid.uuid4())
    now = _now()
    await db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (msg_id, conv_id, role, content, now),
    )
    await db.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id)
    )
    await db.commit()
    return MessageResponse(id=msg_id, conversation_id=conv_id, role=role, content=content, created_at=now)


async def list_messages(db: aiosqlite.Connection, conv_id: str, limit: int = 50) -> list[MessageResponse]:
    async with db.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
        (conv_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [_msg_row_to_response(row) for row in rows]


async def get_recent_messages(db: aiosqlite.Connection, conv_id: str, rounds: int = 10) -> list[MessageResponse]:
    """Fetch last N rounds (N * 2 messages) ordered by created_at ASC for context."""
    limit = rounds * 2
    async with db.execute(
        """SELECT * FROM (
               SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?
           ) ORDER BY created_at ASC""",
        (conv_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [_msg_row_to_response(row) for row in rows]


async def update_conversation_title(db: aiosqlite.Connection, conv_id: str, title: str) -> None:
    now = _now()
    await db.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, now, conv_id),
    )
    await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _conv_row_to_response(row) -> ConversationResponse:
    return ConversationResponse(
        id=row["id"],
        agent_id=row["agent_id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _msg_row_to_response(row) -> MessageResponse:
    return MessageResponse(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )
