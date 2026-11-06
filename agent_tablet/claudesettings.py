"""The Claude Code settings the app passes to every session it starts, with `--settings`.

They layer above the user's own settings for that session only and write nothing under `~/.claude`;
today they carry the app's statusline. The file is rewritten when its content would change, so a
checkout that moved, or another Python, heals on the next command.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

STATUSLINE = Path(__file__).resolve().parent / "statusline.py"


def settings_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "agent-tablet" / "claude-settings.json"


def chain_path() -> Path:
    return settings_path().with_name("chained-statusline.json")


def settings() -> dict:
    return {"statusLine": {"type": "command", "command": shlex.join([sys.executable, str(STATUSLINE)])}}


def ensure() -> Path:
    """The settings file, written if missing or different, and the user's own statusline for the
    app's to chain to. Returns the settings file's path."""
    from . import integrations  # integrations builds on this module

    write_if_changed(chain_path(), json.dumps({"command": integrations.chained_command()}) + "\n")
    return write_if_changed(settings_path(), json.dumps(settings(), indent=2) + "\n")


def write_if_changed(path: Path, text: str) -> Path:
    try:
        if path.read_text(encoding="utf-8") == text:
            return path
    except OSError:
        pass  # missing or unreadable: written below
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(text)
    os.replace(tmp, path)
    return path
