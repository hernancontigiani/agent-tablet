"""Claude Code's statusline command for sessions agent-tablet knows about.

Claude Code runs this after each assistant message with the session's state as JSON on stdin; what
it prints is the bar's text. On the way it leaves two things for the app:

- `$XDG_CACHE_HOME/agent-tablet/sessions/<session_id>.json`, the session's latest context reading;
- one line appended to `$XDG_CACHE_HOME/agent-tablet/usage.jsonl`: cost, lines changed and the
  subscription's limits — what the transcript does not hold.

Runnable on its own with any python3 (`python3 statusline.py`): standard library only, and the
app's clock is loaded from this file's directory. The session file's keys are
`context_fields.SESSION_FIELDS`, which a test holds both sides to. It never fails: a statusline that raises
shows an error in every Claude session, so a bad payload still exits 0 with a fallback bar.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clock

FALLBACK = "agent-tablet"


CHAINED_TIMEOUT = 2.0  # Claude Code cancels a statusline run when the next trigger comes


def _chained_command() -> str | None:
    """The user's own statusline, which the app's runs and shows: written by the app, which knows it."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    try:
        data = json.loads(
            (Path(base) / "agent-tablet" / "chained-statusline.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    command = data.get("command") if isinstance(data, dict) else None
    return command if isinstance(command, str) and command.strip() else None


def chained_bar(stdin: str) -> str | None:
    command = _chained_command()
    if command is None:
        return None
    try:
        result = subprocess.run(
            command, shell=True, input=stdin, capture_output=True, text=True, timeout=CHAINED_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = result.stdout.rstrip("\n")
    return output if result.returncode == 0 and output.strip() else None


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "agent-tablet"


def _get(payload: dict, *keys: str):
    value = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def session_record(payload: dict, stamp: str) -> dict:
    return {
        "session_id": payload.get("session_id"),
        "session_name": payload.get("session_name"),
        "transcript_path": payload.get("transcript_path"),
        "cwd": payload.get("cwd"),
        "model": _get(payload, "model", "id"),
        "percentage": _get(payload, "context_window", "used_percentage"),
        "window": _get(payload, "context_window", "context_window_size"),
        "input_tokens": _get(payload, "context_window", "total_input_tokens"),
        "updated_at": stamp,
    }


def usage_record(payload: dict, stamp: str) -> dict:
    return {
        "at": stamp,
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "model": _get(payload, "model", "id"),
        "cost_usd": _get(payload, "cost", "total_cost_usd"),
        "lines_added": _get(payload, "cost", "total_lines_added"),
        "lines_removed": _get(payload, "cost", "total_lines_removed"),
        "five_hour_pct": _get(payload, "rate_limits", "five_hour", "used_percentage"),
        "seven_day_pct": _get(payload, "rate_limits", "seven_day", "used_percentage"),
    }


def bar(payload: dict) -> str:
    parts = [payload.get("session_name") or str(payload.get("session_id") or FALLBACK)[:8]]
    percentage = _get(payload, "context_window", "used_percentage")
    if isinstance(percentage, int | float):
        parts.append(f"{percentage:.0f}%")
    cost = _get(payload, "cost", "total_cost_usd")
    if isinstance(cost, int | float):
        parts.append(f"${cost:.2f}")
    return " · ".join(parts)


def _write_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(text)
    os.replace(tmp, path)


def record(payload: dict) -> None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id or "/" in session_id:
        return
    stamp = clock.now().astimezone(UTC).isoformat()
    cache = _cache_dir()
    _write_atomically(cache / "sessions" / f"{session_id}.json", json.dumps(session_record(payload, stamp)))
    # One short line with O_APPEND: concurrent sessions appending do not interleave inside a line.
    with open(cache / "usage.jsonl", "a", encoding="utf-8") as usage:
        usage.write(json.dumps(usage_record(payload, stamp)) + "\n")


def main(stdin: str) -> str:
    try:
        payload = json.loads(stdin)
    except ValueError:
        return FALLBACK
    if not isinstance(payload, dict):
        return FALLBACK
    with contextlib.suppress(OSError):  # a full disk costs the app a reading, never the bar
        record(payload)
    return chained_bar(stdin) or bar(payload)


if __name__ == "__main__":
    print(main(sys.stdin.read()))
