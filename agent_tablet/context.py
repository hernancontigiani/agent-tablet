"""How full each session's context window is, for the ring in its row and on its tab.

Exact when the app's statusline script has reported it (a file per session under
`$XDG_CACHE_HOME/agent-tablet/sessions/`); otherwise estimated from the transcript's last assistant
message. The transcript does not say the window's size, so an estimate divides by the last size the
statusline reported for that session, or by 200k when it never did — and says it is an estimate.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib, GObject

from .context_fields import SESSION_FIELDS

DEFAULT_WINDOW = 200_000
_TAIL = 256 * 1024  # the last assistant message is almost always in the last few lines

__all__ = ["DEFAULT_WINDOW", "SESSION_FIELDS", "ContextModel", "ContextReading", "cache_dir", "reading_for"]


@dataclass(frozen=True)
class ContextReading:
    percentage: float
    window: int
    source: str  # "statusline" | "estimate"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "agent-tablet"


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _session_file(cache: Path, session_id: str) -> dict | None:
    try:
        data = json.loads((cache / "sessions" / f"{session_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _assistant_usage(line: bytes) -> tuple[int, datetime] | None:
    if b'"assistant"' not in line:
        return None
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return None
    usage = (entry.get("message") or {}).get("usage")
    at = _parse_time(entry.get("timestamp"))
    if not isinstance(usage, dict) or at is None:
        return None
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    return sum(int(usage.get(key) or 0) for key in keys), at


def last_assistant_usage(transcript: Path) -> tuple[int, datetime] | None:
    """Tokens in the window after the last assistant message (input + cache write + cache read),
    and when it was written. Reads the tail first; the whole file only if the tail has none."""
    try:
        with open(transcript, "rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            for start in (max(0, size - _TAIL), 0):
                handle.seek(start)
                lines = handle.read().splitlines()
                if start > 0:
                    lines = lines[1:]  # the first line of a tail is cut
                for line in reversed(lines):
                    found = _assistant_usage(line)
                    if found is not None:
                        return found
                if start == 0:
                    break
    except OSError:
        return None
    return None


def reading_for(session_id: str, transcript: Path, cache: Path) -> ContextReading | None:
    reported = _session_file(cache, session_id) or {}
    reported_at = _parse_time(reported.get("updated_at"))
    reported_window = reported.get("window")
    window = reported_window if isinstance(reported_window, int) and reported_window > 0 else DEFAULT_WINDOW
    last = last_assistant_usage(transcript)

    percentage = reported.get("percentage")
    fresh = reported_at is not None and (last is None or reported_at >= last[1])
    if isinstance(percentage, int | float) and fresh:
        return ContextReading(float(percentage), window, "statusline")
    if last is None:
        return None
    return ContextReading(round(100 * last[0] / window, 1), window, "estimate")


class ContextModel(GObject.Object):
    """The readings of the sessions the app shows, kept current as the statusline writes.

    `track(session_id, transcript)` adds a session; "changed" fires with its id when its reading
    moves. Files are read off the main thread.
    """

    __gsignals__: ClassVar[dict] = {"changed": (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self, cache: Path | None = None) -> None:
        super().__init__()
        self._cache = cache or cache_dir()
        self._transcripts: dict[str, Path] = {}
        self._readings: dict[str, ContextReading | None] = {}
        self._in_flight: set[str] = set()
        self._again: set[str] = set()
        sessions = self._cache / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        self._monitor = Gio.File.new_for_path(str(sessions)).monitor_directory(
            Gio.FileMonitorFlags.NONE, None
        )
        self._monitor.connect("changed", self._on_file_changed)

    def get(self, session_id: str) -> ContextReading | None:
        return self._readings.get(session_id)

    def track(self, session_id: str, transcript: Path) -> None:
        self._transcripts[session_id] = transcript
        self.refresh(session_id)

    def refresh(self, session_id: str) -> None:
        """Read the session again off the main thread. One read in flight per session: a request
        that arrives meanwhile runs once more when it lands, so a burst costs two reads, not N."""
        transcript = self._transcripts.get(session_id)
        if transcript is None:
            return
        if session_id in self._in_flight:
            self._again.add(session_id)
            return
        self._in_flight.add(session_id)

        def work() -> None:
            reading = reading_for(session_id, transcript, self._cache)
            GLib.idle_add(self._apply, session_id, reading)

        threading.Thread(target=work, daemon=True).start()

    def _apply(self, session_id: str, reading: ContextReading | None) -> bool:
        self._in_flight.discard(session_id)
        if session_id in self._again:
            self._again.discard(session_id)
            self.refresh(session_id)
        if self._readings.get(session_id) != reading:
            self._readings[session_id] = reading
            self.emit("changed", session_id)
        return GLib.SOURCE_REMOVE

    def _on_file_changed(self, _monitor, file: Gio.File, _other, event: Gio.FileMonitorEvent) -> None:
        if event not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED):
            return
        name = file.get_basename() or ""
        if name.endswith(".json") and not name.startswith("."):
            self.refresh(name.removesuffix(".json"))
