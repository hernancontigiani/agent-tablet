"""How much Claude worked: tokens (and, with the turn model, time) per session, read from the
transcripts Claude Code keeps under ~/.claude/projects.

The transcripts hold every assistant response with its token usage, for past sessions too, but a
response is written several times — once per content block, and again when a session is resumed,
forked or replayed by a sidechain — so entries are deduplicated by (message id, request id) across
every file, keeping the non-sidechain copy, then the larger one. A subagent's transcript
(`<session>/subagents/*.jsonl`) counts for its parent.

The numbers live in a cache, `$XDG_CACHE_HOME/agent-tablet/usage.sqlite`: derived data, rebuilt from
the transcripts whenever its schema changes. Each transcript is read from where the last pass
stopped, so a pass costs what was appended since; a file that shrank or was replaced is read again.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import clock, prices

SCHEMA_VERSION = 4
NO_PROJECT = "(no project)"
NO_CATEGORY = "(no category)"
IDLE_AFTER = 2 * 3600  # seconds: a longer gap between two agent activities is not execution
_ASKS_THE_HUMAN = {"AskUserQuestion"}

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE files (
    path TEXT PRIMARY KEY, inode INTEGER NOT NULL, offset INTEGER NOT NULL, state TEXT NOT NULL
);
CREATE TABLE entries (
    message_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    sidechain INTEGER NOT NULL,
    at REAL NOT NULL,
    model TEXT NOT NULL,
    input INTEGER NOT NULL,
    output INTEGER NOT NULL,
    cache_write INTEGER NOT NULL,
    cache_write_1h INTEGER NOT NULL,
    cache_read INTEGER NOT NULL,
    PRIMARY KEY (message_id, request_id)
);
CREATE INDEX entries_session ON entries (session_id);
CREATE TABLE names (session_id TEXT PRIMARY KEY, name TEXT NOT NULL, claude INTEGER NOT NULL);
CREATE TABLE spans (
    file TEXT NOT NULL,
    session_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    kind TEXT NOT NULL,
    start REAL NOT NULL,
    end REAL NOT NULL
);
CREATE INDEX spans_session ON spans (session_id);
CREATE INDEX spans_file ON spans (file);
"""


@dataclass(frozen=True)
class Tokens:
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_write_1h: int = 0  # the part of cache_write held for an hour, priced higher
    cache_read: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_write + self.cache_read


@dataclass(frozen=True)
class TimeSummary:
    execution: dict[str, float]  # seconds, by who started the turn: human, peer, task_notification…
    blocked: float  # seconds waiting on the human: a permission prompt, a question

    @property
    def total_execution(self) -> float:
        return sum(self.execution.values())


def cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "agent-tablet" / "usage.sqlite"


def _bounds(start: datetime | None, end: datetime | None) -> tuple[float, float]:
    return (start.timestamp() if start else float("-inf"), end.timestamp() if end else float("inf"))


def _transcripts(projects: Path) -> Iterator[tuple[Path, str]]:
    """Every transcript with the session it counts for: its own name, or its parent's for a subagent."""
    for path in sorted(projects.glob("*/*.jsonl")):
        yield path, path.stem
    for path in sorted(projects.glob("*/*/subagents/*.jsonl")):
        yield path, path.parent.parent.name


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _seconds(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _entry(entry: dict, session_id: str) -> tuple | None:
    if entry.get("type") != "assistant" or entry.get("isApiErrorMessage"):
        return None
    message = entry.get("message")
    if not isinstance(message, dict):
        return None
    message_id, model, usage = message.get("id"), message.get("model"), message.get("usage")
    if not isinstance(message_id, str) or not isinstance(usage, dict) or model == "<synthetic>":
        return None
    stamp = entry.get("timestamp") if isinstance(entry.get("timestamp"), str) else ""
    at = _seconds(stamp) or 0.0
    request_id = entry.get("requestId")
    if not isinstance(request_id, str) or not request_id:
        # Without a request id the message id alone may repeat across sessions; ids from the API
        # ("msg_…") are unique, anything else also needs its time.
        request_id = f"none:{session_id}" + ("" if message_id.startswith("msg_") else f":{stamp}")
    creation = usage.get("cache_creation")
    if not isinstance(creation, dict):
        creation = {}
    return (
        message_id,
        request_id,
        session_id,
        1 if entry.get("isSidechain") else 0,
        at,
        model if isinstance(model, str) else "",
        _int(usage.get("input_tokens")),
        _int(usage.get("output_tokens")),
        _int(usage.get("cache_creation_input_tokens")),
        _int(creation.get("ephemeral_1h_input_tokens")),
        _int(usage.get("cache_read_input_tokens")),
    )


class UsageCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or cache_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        version = self._version()
        if version != SCHEMA_VERSION:
            self._rebuild()

    def _version(self) -> int | None:
        try:
            row = self._db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
        except sqlite3.DatabaseError:
            return None
        return int(row[0]) if row else None

    def _rebuild(self) -> None:
        tables = [name for (name,) in self._db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        with self._db:
            for name in tables:
                self._db.execute(f'DROP TABLE IF EXISTS "{name}"')
            self._db.executescript(_SCHEMA)
            self._db.execute("INSERT INTO meta VALUES ('schema', ?)", (str(SCHEMA_VERSION),))

    def ingest(self, projects: Path) -> int:
        """Read what each transcript gained since the last pass. Returns the bytes read."""
        read = 0
        with self._db:
            for path, session_id in _transcripts(projects):
                read += self._ingest_file(path, session_id)
        return read

    def _ingest_file(self, path: Path, session_id: str) -> int:
        try:
            stat = path.stat()
        except OSError:
            return 0
        known = self._db.execute(
            "SELECT inode, offset, state FROM files WHERE path = ?", (str(path),)
        ).fetchone()
        fresh = not (known and known[0] == stat.st_ino and stat.st_size >= known[1])
        offset = 0 if fresh else known[1]
        if stat.st_size == offset:
            return 0
        if fresh and known:
            self._db.execute("DELETE FROM spans WHERE file = ?", (str(path),))
        turn = _Turn.load(None if fresh else known[2])
        with open(path, "rb") as handle:
            handle.seek(offset)
            data = handle.read()
        complete = data[: data.rfind(b"\n") + 1]  # a line still being written waits for next time
        for line in complete.splitlines():
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if not isinstance(parsed, dict):
                continue
            entry = _entry(parsed, session_id)
            if entry is not None:
                self._keep(entry)
            self._name(parsed, session_id)
            for origin, kind, start, end in turn.feed(parsed):
                self._db.execute(
                    "INSERT INTO spans VALUES (?, ?, ?, ?, ?, ?)",
                    (str(path), session_id, origin, kind, start, end),
                )
        self._db.execute(
            "INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?)",
            (str(path), stat.st_ino, offset + len(complete), turn.dump()),
        )
        return len(complete)

    def _keep(self, entry: tuple) -> None:
        message_id, sidechain = entry[0], entry[3]
        # A sidechain replaying a response the main thread already has (another request id) adds
        # nothing; a main-thread copy arriving later displaces such replays.
        if (
            sidechain
            and self._db.execute(
                "SELECT 1 FROM entries WHERE message_id = ? AND sidechain = 0", (message_id,)
            ).fetchone()
        ):
            return
        if not sidechain:
            self._db.execute(
                "DELETE FROM entries WHERE message_id = ? AND sidechain = 1 AND request_id != ?",
                (message_id, entry[1]),
            )
        current = self._db.execute(
            "SELECT sidechain, input + output + cache_write + cache_read FROM entries"
            " WHERE message_id = ? AND request_id = ?",
            entry[:2],
        ).fetchone()
        total = entry[6] + entry[7] + entry[8] + entry[10]
        if current is not None:
            current_sidechain, current_total = current
            better = (current_sidechain and not entry[3]) or (
                current_sidechain == entry[3] and total > current_total
            )
            if not better:
                return
        self._db.execute("INSERT OR REPLACE INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", entry)

    def _name(self, entry: dict, session_id: str) -> None:
        """The name Claude has for the session (`-n`, `/rename`) wins over the title it generated."""
        kind = entry.get("type")
        if kind == "custom-title" and isinstance(entry.get("customTitle"), str):
            name, claude = entry["customTitle"].strip(), 1
        elif kind == "ai-title" and isinstance(entry.get("aiTitle"), str):
            name, claude = entry["aiTitle"].strip(), 0
        else:
            return
        current = self._db.execute("SELECT claude FROM names WHERE session_id = ?", (session_id,)).fetchone()
        if name and (current is None or claude >= current[0]):
            self._db.execute("INSERT OR REPLACE INTO names VALUES (?, ?, ?)", (session_id, name, claude))

    def name(self, session_id: str) -> str | None:
        row = self._db.execute("SELECT name FROM names WHERE session_id = ?", (session_id,)).fetchone()
        return row[0] if row else None

    def tokens(self, session_id: str, start: datetime | None = None, end: datetime | None = None) -> Tokens:
        low, high = _bounds(start, end)
        row = self._db.execute(
            "SELECT COALESCE(SUM(input), 0), COALESCE(SUM(output), 0), COALESCE(SUM(cache_write), 0),"
            " COALESCE(SUM(cache_write_1h), 0), COALESCE(SUM(cache_read), 0)"
            " FROM entries WHERE session_id = ? AND at >= ? AND at < ?",
            (session_id, low, high),
        ).fetchone()
        return Tokens(*row)

    def estimated_cost(
        self, session_id: str, start: datetime | None = None, end: datetime | None = None
    ) -> tuple[float, bool]:
        """List-price cost of the session's responses in the period, and whether every model was in
        the price table (a response of an unknown model adds tokens but no cost)."""
        low, high = _bounds(start, end)
        total, all_priced = 0.0, True
        for at, model, input_, output, write, write_1h, read in self._db.execute(
            "SELECT at, model, input, output, cache_write, cache_write_1h, cache_read FROM entries"
            " WHERE session_id = ? AND at >= ? AND at < ?",
            (session_id, low, high),
        ):
            when = datetime.fromtimestamp(at, tz=UTC)
            priced = prices.cost(
                model,
                when,
                input=input_,
                output=output,
                cache_write=write,
                cache_write_1h=write_1h,
                cache_read=read,
            )
            if priced is None:
                all_priced = False
            else:
                total += priced
        return total, all_priced

    def sessions(self, start: datetime | None = None, end: datetime | None = None) -> set[str]:
        """Every session with a response or some execution time in the period."""
        low, high = _bounds(start, end)
        found = {
            sid
            for (sid,) in self._db.execute(
                "SELECT DISTINCT session_id FROM entries WHERE at >= ? AND at < ?", (low, high)
            )
        }
        found |= {
            sid
            for (sid,) in self._db.execute(
                "SELECT DISTINCT session_id FROM spans WHERE end > ? AND start < ?", (low, high)
            )
        }
        return found

    def time(
        self, session_id: str, start: datetime | None = None, end: datetime | None = None
    ) -> TimeSummary:
        """Execution and blocked time, clipped to [start, end) — a day is two local midnights."""
        low = start.timestamp() if start else float("-inf")
        high = end.timestamp() if end else float("inf")
        execution: dict[str, float] = {}
        blocked = 0.0
        for origin, kind, span_start, span_end in self._db.execute(
            "SELECT origin, kind, start, end FROM spans WHERE session_id = ?", (session_id,)
        ):
            seconds = max(0.0, min(span_end, high) - max(span_start, low))
            if not seconds:
                continue
            if kind == "blocked":
                blocked += seconds
            else:
                execution[origin] = execution.get(origin, 0.0) + seconds
        return TimeSummary(execution, blocked)


class _Turn:
    """The turn being read, carried across passes: who started it, the last agent activity, and the
    tool calls still waiting for their result."""

    def __init__(self, origin: str | None = None, last: float | None = None, pending: dict | None = None):
        self.origin = origin
        self.last = last
        self.pending: dict[str, list] = pending or {}  # tool_use id -> [when, asks the human]

    @classmethod
    def load(cls, state: str | None) -> _Turn:
        try:
            data = json.loads(state) if state else {}
        except ValueError:
            data = {}
        return cls(data.get("origin"), data.get("last"), data.get("pending"))

    def dump(self) -> str:
        return json.dumps({"origin": self.origin, "last": self.last, "pending": self.pending})

    def feed(self, entry: dict) -> list[tuple[str, str, float, float]]:
        """The spans this entry closes: (origin, "execution" | "blocked", start, end)."""
        at = _seconds(entry.get("timestamp"))
        if at is None:
            return []
        if entry.get("type") == "user" and isinstance(entry.get("turnOrigin"), str):
            self.origin, self.last, self.pending = entry["turnOrigin"], at, {}
            return []
        if self.origin is None or self.last is None:
            return []
        content = (entry.get("message") or {}).get("content")
        blocks = content if isinstance(content, list) else []
        if entry.get("type") == "assistant":
            for block in blocks:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and isinstance(block.get("id"), str)
                ):
                    self.pending[block["id"]] = [at, block.get("name") in _ASKS_THE_HUMAN]
        elif entry.get("type") == "user" and (
            entry.get("toolUseResult") is not None
            or any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks)
        ):
            decision = entry.get("permissionDecision")
            human_decided = isinstance(decision, dict) and str(decision.get("source", "")).startswith("user")
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    asked = self.pending.pop(str(block.get("tool_use_id")), None)
                    if asked is not None and (asked[1] or human_decided):
                        self.last = at
                        return [(self.origin, "blocked", asked[0], at)]
        else:
            return []  # not an agent activity: meta entries, notes, commands
        spans = []
        if at - self.last <= IDLE_AFTER:
            spans.append((self.origin, "execution", self.last, at))
        self.last = at
        return spans


# -- the statusline's figures (usage.jsonl, written by statusline.py) ---------------------------


def usage_log_path() -> Path:
    return cache_path().with_name("usage.jsonl")


def _usage_lines(path: Path) -> Iterator[dict]:
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if isinstance(data, dict):
                    yield data
    except OSError:
        return


def statusline_costs(path: Path, start: datetime | None, end: datetime | None) -> dict[str, float]:
    """The exact cost each session accrued in the period, from the statusline's running totals.
    A total that drops is a /clear starting over from zero, so what it shows next is all new."""
    low, high = _bounds(start, end)
    previous: dict[str, float] = {}
    accrued: dict[str, float] = {}
    for line in _usage_lines(path):
        session_id, cost, at = line.get("session_id"), line.get("cost_usd"), _seconds(line.get("at"))
        if not isinstance(session_id, str) or not isinstance(cost, int | float) or at is None:
            continue
        before = previous.get(session_id, 0.0)
        increment = cost - before if cost >= before else cost
        previous[session_id] = cost
        if low <= at < high:
            accrued[session_id] = accrued.get(session_id, 0.0) + increment
    return accrued


def latest_limits(path: Path) -> tuple[float, float] | None:
    """The subscription's 5-hour and 7-day use, in %, as the statusline last reported them."""
    found = None
    for line in _usage_lines(path):
        five, seven = line.get("five_hour_pct"), line.get("seven_day_pct")
        if isinstance(five, int | float) and isinstance(seven, int | float):
            found = (float(five), float(seven))
    return found


# -- the report ---------------------------------------------------------------------------------

PERIODS = {"today": 1, "7d": 7, "30d": 30}


def period_bounds(period: str, now: datetime) -> tuple[datetime, datetime]:
    """[start, end) in local days: from midnight `days - 1` days ago to the coming midnight."""
    days = PERIODS[period]
    today = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=days - 1), today + timedelta(days=1)


@dataclass
class Node:
    label: str
    kind: str  # "project" | "category" | "session"
    execution: dict[str, float]
    blocked: float
    tokens: Tokens
    cost: float
    cost_exact: bool  # every session under it reported its cost through the statusline
    all_priced: bool  # every model under it was in the price table
    children: list[Node]

    @property
    def total_execution(self) -> float:
        return sum(self.execution.values())

    def to_json(self) -> dict:
        return {
            "label": self.label,
            "kind": self.kind,
            "execution_seconds": self.execution,
            "blocked_seconds": self.blocked,
            "tokens": vars(self.tokens),
            "cost_usd": self.cost,
            "cost_exact": self.cost_exact,
            "all_priced": self.all_priced,
            "children": [child.to_json() for child in self.children],
        }


@dataclass
class Report:
    start: datetime
    end: datetime
    nodes: list[Node]
    limits: tuple[float, float] | None

    def to_json(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "nodes": [node.to_json() for node in self.nodes],
            "limits": list(self.limits) if self.limits else None,
        }


def _sum(label: str, kind: str, children: list[Node]) -> Node:
    execution: dict[str, float] = {}
    for child in children:
        for origin, seconds in child.execution.items():
            execution[origin] = execution.get(origin, 0.0) + seconds
    tokens = Tokens(*(sum(getattr(c.tokens, f) for c in children) for f in Tokens.__dataclass_fields__))
    return Node(
        label,
        kind,
        execution,
        sum(c.blocked for c in children),
        tokens,
        sum(c.cost for c in children),
        all(c.cost_exact for c in children),
        all(c.all_priced for c in children),
        children,
    )


def report(
    cache: UsageCache,
    start: datetime,
    end: datetime,
    memberships: dict[str, str],
    usage_log: Path,
    names: dict[str, str] | None = None,
) -> Report:
    """Project → category → session for [start, end). `memberships` maps a session to its project's
    name; a session in none goes under NO_PROJECT. Categories do not exist yet: NO_CATEGORY."""
    exact = statusline_costs(usage_log, start, end)
    by_project: dict[str, list[Node]] = {}
    for session_id in sorted(cache.sessions(start, end)):
        time = cache.time(session_id, start, end)
        estimate, all_priced = cache.estimated_cost(session_id, start, end)
        label = (names or {}).get(session_id) or cache.name(session_id) or session_id[:8]
        node = Node(
            label,
            "session",
            time.execution,
            time.blocked,
            cache.tokens(session_id, start, end),
            exact.get(session_id, estimate),
            session_id in exact,
            all_priced,
            [],
        )
        by_project.setdefault(memberships.get(session_id, NO_PROJECT), []).append(node)
    nodes = []
    for project in sorted(by_project, key=lambda name: (name == NO_PROJECT, name.casefold())):
        sessions = sorted(by_project[project], key=lambda n: -n.total_execution)
        nodes.append(_sum(project, "project", [_sum(NO_CATEGORY, "category", sessions)]))
    return Report(start, end, nodes, latest_limits(usage_log))


def duration(seconds: float) -> str:
    """Hours with a decimal from one hour up; whole minutes below, so a short session is not 0.0h."""
    return f"{seconds / 3600:.1f}h" if seconds >= 3600 else f"{seconds / 60:.0f}m"


def _tokens(count: int) -> str:
    return f"{count / 1_000_000:.1f}M" if count >= 1_000_000 else f"{count / 1000:.0f}k"


def print_report(result: Report, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result.to_json(), indent=2))
        return
    print(f"{'':44} {'exec':>7} {'blocked':>8} {'tokens':>8} {'cost':>9}")

    def line(node: Node, depth: int) -> None:
        cost = ("$" if node.cost_exact else "~$") + f"{node.cost:.2f}" + ("" if node.all_priced else "+")
        name = ("  " * depth + node.label)[:44]
        execution, blocked = duration(node.total_execution), duration(node.blocked)
        print(f"{name:44} {execution:>7} {blocked:>8} {_tokens(node.tokens.total):>8} {cost:>9}")
        for child in node.children:
            line(child, depth + 1)

    for node in result.nodes:
        line(node, 0)
    if result.limits:
        print(f"\nsubscription: 5-hour {result.limits[0]:.0f}%, 7-day {result.limits[1]:.0f}%")
    print("~ = list-price estimate; + = a model without a price")


def _memberships(config_dir: Path) -> dict[str, str]:
    """Read projects.json read-only: a session's project name, by id."""
    try:
        data = json.loads((config_dir / "projects.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    found = {}
    for project in data.get("projects", []) if isinstance(data, dict) else []:
        if isinstance(project, dict) and isinstance(project.get("name"), str):
            for member in project.get("members") or []:
                if isinstance(member, str):
                    found[member] = project["name"]
    return found


def main(argv: list[str] | None = None) -> int:
    import argparse

    from . import sessions

    parser = argparse.ArgumentParser(prog="agent-tablet usage", description="Execution time and tokens.")
    parser.add_argument("--period", choices=sorted(PERIODS), default="7d")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    cache = UsageCache()
    cache.ingest(sessions.CLAUDE_PROJECTS_DIR)
    start, end = period_bounds(args.period, clock.now())
    config = Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")) / "agent-tablet"
    print_report(report(cache, start, end, _memberships(config), usage_log_path()), as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
