"""Persistent app state: custom names, emojis, hidden sessions, settings.

Everything lives in our own config file — the agents' session data is never
modified.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .projects import FILE_NAME as PROJECTS_FILE
from .projects import Projects

_CONFIG_BASE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
_CONFIG_DIR = _CONFIG_BASE / "agent-tablet"
# The app this was forked from, under its current and its pre-rebrand name, newest first. Its
# state is imported once so names set there survive the switch; it is never written.
_ORIGINAL_CONFIG_DIRS = (
    _CONFIG_BASE / "agent-session-manager",
    _CONFIG_BASE / "claude-session-manager",
)
_STATE_FILE = _CONFIG_DIR / "state.json"
_LEGACY_NAMES_FILE = _CONFIG_BASE / "claude-session-manager" / "names.json"


def _migrate_old_config() -> None:
    """One-time: copy the original app's state.json when we have none of our own."""
    if _STATE_FILE.exists():
        return
    for old_dir in _ORIGINAL_CONFIG_DIRS:
        old_state = old_dir / "state.json"
        if old_state.exists():
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_state, _STATE_FILE)
            return


DEFAULT_SETTINGS = {
    "font": "",  # empty = VTE default
    "scrollback": 10_000,
    "color_scheme": "system",  # system | light | dark
    "terminal_theme": "Default",  # VTE color palette (see themes.py)
    "ui_style": "tui",  # tui (terminal-workspace look) | classic (plain libadwaita)
    "language": "",  # UI language code; "" = follow the system locale
    "notify_idle": True,  # notify when a background session goes quiet
    "notify_sound": True,  # play a sound when a background agent finishes / gets blocked
    "new_session_dir": "",  # remembered folder for new sessions (empty = ask)
    "sidebar_width": 300,  # persisted sidebar pane width in px
    "reopen_tabs": True,  # on start, resume the sessions that were in tabs, in their windows
}


class AppState:
    def __init__(self) -> None:
        self.names: dict[str, str] = {}
        self.emojis: dict[str, str] = {}
        self.hidden: set[str] = set()
        self.settings: dict = dict(DEFAULT_SETTINGS)
        self._load()
        self.projects_file = _CONFIG_DIR / PROJECTS_FILE
        self.projects = Projects.load(self.projects_file)

    # -- persistence ---------------------------------------------------

    def _load(self) -> None:
        _migrate_old_config()
        data: dict = {}
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # one-time migration from the old names-only store
            try:
                data = {"names": json.loads(_LEGACY_NAMES_FILE.read_text(encoding="utf-8"))}
            except (OSError, json.JSONDecodeError):
                data = {}
        self.names = dict(data.get("names") or {})
        self.emojis = dict(data.get("emojis") or {})
        self.hidden = set(data.get("hidden") or [])
        self.settings = {**DEFAULT_SETTINGS, **(data.get("settings") or {})}

    def save(self) -> None:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "names": self.names,
            "emojis": self.emojis,
            "hidden": sorted(self.hidden),
            "settings": self.settings,
        }
        tmp = _STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_STATE_FILE)

    def save_projects(self) -> None:
        self.projects.save(self.projects_file)

    # -- names -----------------------------------------------------------

    def get_name(self, session_id: str) -> str | None:
        return self.names.get(session_id)

    def set_name(self, session_id: str, name: str) -> None:
        name = name.strip()
        if name:
            self.names[session_id] = name
        else:
            self.names.pop(session_id, None)
        self.save()

    # -- emojis ------------------------------------------------------------

    def get_emoji(self, session_id: str) -> str | None:
        return self.emojis.get(session_id)

    def set_emoji(self, session_id: str, emoji: str) -> None:
        emoji = emoji.strip()
        if emoji:
            self.emojis[session_id] = emoji
        else:
            self.emojis.pop(session_id, None)
        self.save()

    # -- hidden ------------------------------------------------------------

    def is_hidden(self, session_id: str) -> bool:
        return session_id in self.hidden

    def set_hidden(self, session_id: str, hidden: bool) -> None:
        if hidden:
            self.hidden.add(session_id)
        else:
            self.hidden.discard(session_id)
        self.save()

    # -- settings ------------------------------------------------------------

    def get_setting(self, key: str) -> Any:
        return self.settings.get(key, DEFAULT_SETTINGS.get(key))

    def set_setting(self, key: str, value) -> None:
        self.settings[key] = value
        self.save()
