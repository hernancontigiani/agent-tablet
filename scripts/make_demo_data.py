#!/usr/bin/env python3
"""Generate fake Claude Code sessions for screenshots and demos.

Usage:
    python3 scripts/make_demo_data.py [--root DIR]     (default /tmp/csm-demo)
    XDG_CONFIG_HOME=/tmp/csm-demo/config \\
        CSM_PROJECTS_DIR=/tmp/csm-demo/projects \\
        CSM_CLAUDE_CONFIG=/tmp/csm-demo/claude.json \\
        python3 -m agent_tablet
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path

DEFAULT_ROOT = Path("/tmp/csm-demo")

# (project, preview prompt, age, custom name|None, emoji|None, mcp server used|None)
SESSIONS = [
    (
        "portfolio-website",
        "Redesign the hero section with a dark theme and subtle animations",
        300,
        "Homepage redesign",
        "🎨",
        None,
    ),
    (
        "portfolio-website",
        "Fix the contact form validation, emails with a plus sign are rejected",
        7200,
        None,
        None,
        None,
    ),
    ("todo-api", "Add JWT authentication to the API with refresh tokens", 5400, "JWT auth", "🔐", "postgres"),
    ("todo-api", "Write integration tests for the todo endpoints", 86400, None, None, None),
    ("dotfiles", "Migrate my neovim configuration from vimscript to lua", 172800, None, None, None),
    (
        "snake-game",
        "Build a snake game in pygame with a persistent high score list",
        259200,
        "Snake",
        "🐍",
        None,
    ),
    (
        "data-pipeline",
        "Optimize the CSV import, it is too slow on files over 1GB",
        518400,
        None,
        None,
        "linear",
    ),
]

# Projects, by the prompts of their sessions: one mixing two folders with a group, one in a single
# folder, and the empty Default.
PROJECTS = [
    {
        "name": "Client work",
        "prompts": [
            "Redesign the hero section with a dark theme and subtle animations",
            "Add JWT authentication to the API with refresh tokens",
            "Write integration tests for the todo endpoints",
        ],
        "group": (
            "api pair",
            "#5ec4b6",
            [
                "Add JWT authentication to the API with refresh tokens",
                "Write integration tests for the todo endpoints",
            ],
        ),
    },
    {"name": "Dotfiles", "prompts": ["Migrate my neovim configuration from vimscript to lua"], "group": None},
]

# Fake MCP servers, so the MCP browser and details show realistic-but-fake data.
MCP_GLOBAL = {
    "github": {"type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]},
    "linear": {"type": "http", "url": "https://mcp.linear.app/sse"},
    "filesystem": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
    },
}
MCP_PER_PROJECT = {
    "/home/demo/projects/todo-api": {
        "postgres": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres"],
        },
    },
}


# Sessions named inside Claude (`claude -n`, `/rename`), by their prompt: the list shows this name
# over any name set in the app.
CLAUDE_NAMES = {"Write integration tests for the todo endpoints": "todo-api-tests"}


def make_transcript(cwd: str, prompt: str, timestamp: float, mcp_server: str | None) -> tuple[str, str]:
    iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(timestamp))
    session_id = str(uuid.uuid4())
    content: list[dict] = [{"type": "text", "text": "On it — here's the plan, then I'll start."}]
    if mcp_server:
        content.append({"type": "tool_use", "id": "t1", "name": f"mcp__{mcp_server}__query", "input": {}})
    lines = [
        {"type": "mode", "sessionId": session_id},
        {
            "type": "user",
            "cwd": cwd,
            "sessionId": session_id,
            "timestamp": iso,
            "message": {"role": "user", "content": prompt},
        },
        {
            "type": "assistant",
            "cwd": cwd,
            "sessionId": session_id,
            "timestamp": iso,
            "message": {
                "role": "assistant",
                "model": "claude-opus-4-8",
                "content": content,
                "usage": {"input_tokens": 1200, "output_tokens": 400, "cache_read_input_tokens": 9000},
            },
        },
    ]
    if prompt in CLAUDE_NAMES:
        lines.append({"type": "custom-title", "customTitle": CLAUDE_NAMES[prompt], "sessionId": session_id})
    return session_id, "\n".join(json.dumps(line) for line in lines) + "\n"


def write_demo(root: Path) -> None:
    projects_dir = root / "projects"
    config_dir = root / "config" / "agent-tablet"
    projects_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    names: dict[str, str] = {}
    ids: dict[str, str] = {}
    emojis: dict[str, str] = {}
    now = time.time()

    for project, prompt, age, custom_name, emoji, mcp_server in SESSIONS:
        cwd = f"/home/demo/projects/{project}"
        project_dir = projects_dir / cwd.replace("/", "-")
        project_dir.mkdir(exist_ok=True)
        mtime = now - age
        session_id, content = make_transcript(cwd, prompt, mtime, mcp_server)
        path = project_dir / f"{session_id}.jsonl"
        path.write_text(content, encoding="utf-8")
        os.utime(path, (mtime, mtime))
        ids[prompt] = session_id
        if custom_name:
            names[session_id] = custom_name
        if emoji:
            emojis[session_id] = emoji

    (config_dir / "state.json").write_text(
        json.dumps(
            {"names": names, "emojis": emojis, "hidden": [], "settings": {}},
            indent=2,
        ),
        encoding="utf-8",
    )

    projects = [{"id": "default", "name": "Default", "members": [], "groups": []}]
    for number, spec in enumerate(PROJECTS, start=1):
        groups = []
        if spec["group"]:
            name, color, prompts = spec["group"]
            groups.append({"name": name, "color": color, "members": [ids[p] for p in prompts]})
        members = [ids[p] for p in spec["prompts"]]
        projects.append({"id": f"demo-{number}", "name": spec["name"], "members": members, "groups": groups})
    (config_dir / "projects.json").write_text(
        json.dumps({"version": 1, "current": "demo-1", "projects": projects, "windows": []}, indent=2),
        encoding="utf-8",
    )

    (root / "claude.json").write_text(
        json.dumps({"mcpServers": MCP_GLOBAL, "projects": MCP_PER_PROJECT}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fake Claude Code sessions.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="output directory")
    root = parser.parse_args().root
    write_demo(root)
    print(f"Demo data written to {root}")
    print("Launch with:")
    print(
        f"  XDG_CONFIG_HOME={root}/config CSM_PROJECTS_DIR={root}/projects "
        f"CSM_CLAUDE_CONFIG={root}/claude.json python3 -m agent_tablet"
    )


if __name__ == "__main__":
    main()
