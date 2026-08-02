import os
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import init_db
from app.agents.api import router as agents_api_router
from app.agents.router import router as agents_router
from app.chat.api import router as chat_api_router
from app.chat.router import router as chat_router
from app.runner.manager import RunnerManager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "shrimpwar.db")
WORKSPACES_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspaces")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    app.state.db = await aiosqlite.connect(DB_PATH)
    app.state.db.row_factory = aiosqlite.Row
    await init_db(app.state.db)
    app.state.workspaces_root = WORKSPACES_ROOT
    os.makedirs(WORKSPACES_ROOT, exist_ok=True)
    from app.agents.service import update_agent_status

    async def on_runner_complete(agent_key: str, status: str) -> None:
        await update_agent_status(app.state.db, agent_key, status)

    app.state.runner = RunnerManager(on_complete=on_runner_complete)
    app.state.templates = Jinja2Templates(directory=TEMPLATES_DIR)
    yield
    await app.state.db.close()


app = FastAPI(title="ShrimpWar", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

app.include_router(agents_router)
app.include_router(chat_router)
app.include_router(agents_api_router, prefix="/api")
app.include_router(chat_api_router, prefix="/api")


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/agents")
