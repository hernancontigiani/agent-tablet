"""What the app may add to Claude Code's own settings (`~/.claude/settings.json`), one piece at a
time, each accepted by the user and removable on its own.

Today one piece: the app's statusline for every Claude session, including the ones started outside
the app (those it starts already get it through `--settings`). Installing keeps a dated copy of the
file, records what it wrote and the statusline it replaced; removing puts that one back, and only
if the file still holds what the app wrote — a file the user changed since is left alone.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import claudesettings, clock
from .i18n import _


class IntegrationError(Exception):
    """A change the app refuses to make; its message is for the user."""


def user_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "agent-tablet"


def record_path() -> Path:
    return _state_dir() / "integrations.json"


def backup_dir() -> Path:
    return _state_dir() / "settings-backup"


def _ours() -> dict:
    return claudesettings.settings()["statusLine"]


def _read_settings() -> dict:
    path = user_settings_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as err:
        raise IntegrationError(_("{path} could not be read.").format(path=path)) from err
    try:
        data = json.loads(text)
    except ValueError as err:
        raise IntegrationError(
            _("{path} is not valid JSON; it was left as it is.").format(path=path)
        ) from err
    if not isinstance(data, dict):
        raise IntegrationError(
            _("{path} does not hold a JSON object; it was left as it is.").format(path=path)
        )
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def _record() -> dict:
    try:
        data = json.loads(record_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def statusline_installed() -> bool:
    entry = _record().get("statusline")
    if not isinstance(entry, dict):
        return False
    try:
        return _read_settings().get("statusLine") == entry.get("installed")
    except IntegrationError:
        return False


def install_statusline() -> None:
    settings = _read_settings()
    ours = _ours()
    if settings.get("statusLine") == ours and statusline_installed():
        return
    if user_settings_path().exists():
        stamp = clock.now().strftime("%Y%m%d-%H%M%S")
        backup = backup_dir() / f"settings-{stamp}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(user_settings_path().read_bytes())
    previous = settings.get("statusLine")
    entry = {"installed": ours, "previous": None if previous == ours else previous}
    settings["statusLine"] = ours
    _write_json(user_settings_path(), settings)
    _write_json(record_path(), {**_record(), "statusline": entry})
    claudesettings.ensure()


def remove_statusline() -> None:
    record = _record()
    entry = record.get("statusline")
    if not isinstance(entry, dict):
        return
    settings = _read_settings()
    if settings.get("statusLine") != entry.get("installed"):
        raise IntegrationError(
            _("The status line in {path} changed since it was installed; it was left as it is.").format(
                path=user_settings_path()
            )
        )
    previous = entry.get("previous")
    if previous is None:
        settings.pop("statusLine", None)
    else:
        settings["statusLine"] = previous
    _write_json(user_settings_path(), settings)
    record.pop("statusline")
    _write_json(record_path(), record)
    claudesettings.ensure()


def chained_command() -> str | None:
    """The user's own statusline command, which the app's statusline runs and shows instead of its
    own bar: the one the global install replaced, or the one `--settings` outranks."""
    entry = _record().get("statusline")
    candidate = entry.get("previous") if isinstance(entry, dict) else None
    if candidate is None:
        try:
            candidate = _read_settings().get("statusLine")
        except IntegrationError:
            return None
    if not isinstance(candidate, dict) or candidate == _ours():
        return None
    command = candidate.get("command")
    return command if isinstance(command, str) and command.strip() else None
