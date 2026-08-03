import aiosqlite


async def init_db(db: aiosqlite.Connection):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'admin',
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            avatar TEXT NOT NULL DEFAULT '',
            agent_key TEXT NOT NULL UNIQUE,
            workspace_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'idle',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL REFERENCES agents(id),
            title TEXT NOT NULL DEFAULT '新对话',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'admin',
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            dsl TEXT NOT NULL DEFAULT '{}',
            orchestrator_agent_id TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("PRAGMA foreign_keys = ON")
    await db.commit()
