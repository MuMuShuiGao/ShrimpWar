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
    await db.commit()
