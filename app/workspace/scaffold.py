import json
import os
from datetime import datetime, timezone

WORKSPACE_FILES = [
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
    "AGENTS.md",
    "TOOLS.md",
    "MEMORY.md",
    "BOOTSTRAP.md",
    "HEARTBEAT.md",
]

DEFAULT_CONFIG = {
    "platform": "claude-code",
    "model": "claude-sonnet-4-6",
    "temperature": 0.7,
    "maxTokens": 4096,
}


def scaffold(workspace_root: str, agent_key: str, name: str, description: str = "", agent_id: str = "") -> str:
    """Create a new agent workspace directory with all scaffold files. Returns workspace_path."""
    workspace_path = os.path.join(workspace_root, agent_key)
    os.makedirs(workspace_path, exist_ok=False)
    os.makedirs(os.path.join(workspace_path, "skills"), exist_ok=True)

    for filename in WORKSPACE_FILES:
        filepath = os.path.join(workspace_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("")

    config = {
        **DEFAULT_CONFIG,
        "agentId": agent_id,
        "name": name,
        "description": description,
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    config_path = os.path.join(workspace_path, "agent.config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return workspace_path


def read_file(workspace_path: str, filename: str) -> str:
    filepath = os.path.join(workspace_path, filename)
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def write_file(workspace_path: str, filename: str, content: str) -> None:
    filepath = os.path.join(workspace_path, filename)
    dirname = os.path.dirname(filepath)
    os.makedirs(dirname, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def read_config(workspace_path: str) -> dict:
    filepath = os.path.join(workspace_path, "agent.config.json")
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_config(workspace_path: str, config: dict) -> None:
    config["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    filepath = os.path.join(workspace_path, "agent.config.json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
