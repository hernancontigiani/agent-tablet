import json

import pytest

from agent_tablet.sessions import (
    TITLE_SCANS,
    Session,
    configured_mcp_servers,
    discover_sessions,
    export_markdown,
    parse_details,
    read_mcp_config,
    read_titles,
    session_from_file,
    session_title,
)
from tests.conftest import make_transcript_lines


def test_session_from_file_claude(tmp_path):
    p = tmp_path / "abc.jsonl"
    p.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}, "cwd": "/proj"}) + "\n",
        encoding="utf-8",
    )
    session = session_from_file(p)
    assert session is not None
    assert session.session_id == "abc"
    assert session.provider == "claude"  # detected from top-level "type"
    assert session.cwd == "/proj"


def test_session_from_file_cursor(tmp_path):
    p = tmp_path / "xyz.jsonl"
    p.write_text(
        json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "hi"}]}}) + "\n",
        encoding="utf-8",
    )
    session = session_from_file(p)
    assert session is not None and session.provider == "cursor"  # from top-level "role"


def test_session_from_file_missing(tmp_path):
    assert session_from_file(tmp_path / "nope.jsonl") is None


@pytest.fixture(autouse=True)
def _isolate_claude(monkeypatch):
    """These are Claude-discovery tests: force Claude available regardless of
    PATH, and keep Cursor from scanning the real ~/.cursor."""
    import agent_tablet.providers as providers_mod

    monkeypatch.setattr(providers_mod.ClaudeProvider, "available", lambda self: True)
    monkeypatch.setattr(providers_mod.CursorProvider, "available", lambda self: False)


def test_discover_finds_only_real_sessions(projects_dir):
    _root, ids = projects_dir
    sessions = discover_sessions()
    assert len(sessions) == 3  # noise files excluded
    assert {s.session_id for s in sessions} == set(ids.values())


def test_discover_extracts_cwd_and_preview(projects_dir):
    _root, ids = projects_dir
    by_id = {s.session_id: s for s in discover_sessions()}
    alpha = by_id[ids["alpha1"]]
    assert alpha.cwd == "/home/user/alpha"
    assert alpha.preview == "Build the alpha feature"
    assert alpha.project_name == "alpha"


def test_discover_sorted_newest_first(projects_dir):
    sessions = discover_sessions()
    mtimes = [s.mtime for s in sessions]
    assert mtimes == sorted(mtimes, reverse=True)


def test_parse_details_counts(projects_dir):
    _root, ids = projects_dir
    session = next(s for s in discover_sessions() if s.session_id == ids["alpha1"])
    details = parse_details(session.jsonl_path)
    assert details.user_messages == 1  # tool_result entry is not a user message
    assert details.assistant_messages == 1
    assert details.tool_calls == 1
    assert details.models == ["claude-opus-4-8"]
    assert details.input_tokens == 100
    assert details.output_tokens == 50
    assert details.cache_read_tokens == 2000
    assert details.first_timestamp == "2026-06-01T10:00:00.000Z"
    assert details.last_timestamp == "2026-06-01T10:01:00.000Z"
    assert details.file_size > 0


def test_parse_details_collects_recent_messages(projects_dir):
    _root, ids = projects_dir
    session = next(s for s in discover_sessions() if s.session_id == ids["alpha1"])
    details = parse_details(session.jsonl_path)
    # First user text message + the assistant's text reply; tool_result is skipped.
    assert ("user", "Build the alpha feature") in details.messages
    assert ("assistant", "Hello!") in details.messages
    assert all(role in ("user", "assistant") for role, _ in details.messages)


def test_parse_details_counts_mcp_tools(tmp_path):
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "model": "claude-opus-4-8",
            "content": [
                {"type": "tool_use", "id": "1", "name": "mcp__gitlab__get_issue", "input": {}},
                {"type": "tool_use", "id": "2", "name": "mcp__gitlab__list_issues", "input": {}},
                {"type": "tool_use", "id": "3", "name": "Bash", "input": {}},
            ],
        },
    }
    path = tmp_path / "s.jsonl"
    path.write_text(json.dumps(entry), encoding="utf-8")
    details = parse_details(path)
    assert details.mcp_tools == {"gitlab": 2}
    assert details.tool_calls == 3


def test_configured_mcp_servers(monkeypatch, tmp_path):
    import agent_tablet.sessions as sessions_mod

    config = tmp_path / "claude.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {"gitlab": {}, "playwright": {}},
                "projects": {"/home/u/proj": {"mcpServers": {"local-thing": {}}}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sessions_mod, "CLAUDE_CONFIG", config)
    assert configured_mcp_servers("/home/u/proj") == ["gitlab", "local-thing", "playwright"]
    assert configured_mcp_servers("/unknown") == ["gitlab", "playwright"]
    assert configured_mcp_servers(None) == ["gitlab", "playwright"]


def test_read_mcp_config(monkeypatch, tmp_path):
    import agent_tablet.sessions as sessions_mod

    config = tmp_path / "claude.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "gitlab": {"type": "stdio", "command": "npx", "args": ["-y", "gitlab-mcp"]},
                    "linear": {"type": "http", "url": "https://mcp.linear.app/sse"},
                },
                "projects": {
                    "/home/u/proj": {"mcpServers": {"local-thing": {"command": "./serve"}}},
                    "/home/u/empty": {"mcpServers": {}},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sessions_mod, "CLAUDE_CONFIG", config)
    mcp = read_mcp_config()
    assert not mcp.is_empty
    assert [s.name for s in mcp.global_servers] == ["gitlab", "linear"]
    assert mcp.global_servers[0].summary == "stdio · npx -y gitlab-mcp"
    assert mcp.global_servers[1].summary == "http · https://mcp.linear.app/sse"
    # only the project with servers shows up
    assert [p for p, _ in mcp.project_servers] == ["/home/u/proj"]


def test_read_mcp_config_missing_file(monkeypatch, tmp_path):
    import agent_tablet.sessions as sessions_mod

    monkeypatch.setattr(sessions_mod, "CLAUDE_CONFIG", tmp_path / "nope.json")
    assert read_mcp_config().is_empty


def test_configured_mcp_servers_missing_file(monkeypatch, tmp_path):
    import agent_tablet.sessions as sessions_mod

    monkeypatch.setattr(sessions_mod, "CLAUDE_CONFIG", tmp_path / "nope.json")
    assert configured_mcp_servers("/whatever") == []


def test_tail_state_waiting(monkeypatch, tmp_path):
    import agent_tablet.sessions as sessions_mod

    root = tmp_path / "projects" / "-home-u-proj"
    root.mkdir(parents=True)
    monkeypatch.setattr(sessions_mod, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")

    def write(name, last_assistant_text):
        sid = name
        lines = [
            {"type": "user", "cwd": "/home/u/proj", "message": {"content": "do the thing"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-8",
                    "content": [{"type": "text", "text": last_assistant_text}],
                },
            },
        ]
        (root / f"{sid}.jsonl").write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

    # valid UUID-shaped stems are required by discovery
    waiting_id = "11111111-1111-1111-1111-111111111111"
    done_id = "22222222-2222-2222-2222-222222222222"
    write(waiting_id, "Which database should I use, Postgres or SQLite?")
    write(done_id, "Done — all tests pass.")

    states = {s.session_id: s.state for s in sessions_mod.discover_sessions()}
    assert states[waiting_id] == "waiting"
    assert states[done_id] == ""


def test_tail_state_interrupted(monkeypatch, tmp_path):
    import agent_tablet.sessions as sessions_mod

    root = tmp_path / "projects" / "-home-u-proj"
    root.mkdir(parents=True)
    monkeypatch.setattr(sessions_mod, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")
    sid = "44444444-4444-4444-4444-444444444444"
    lines = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Working on it…"}]}},
        {"type": "user", "cwd": "/home/u/proj", "message": {"content": "[Request interrupted by user]"}},
    ]
    (root / f"{sid}.jsonl").write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    state = next(s.state for s in sessions_mod.discover_sessions() if s.session_id == sid)
    assert state == "interrupted"


def test_tail_state_user_replied_after_question(monkeypatch, tmp_path):
    import agent_tablet.sessions as sessions_mod

    root = tmp_path / "projects" / "-home-u-proj"
    root.mkdir(parents=True)
    monkeypatch.setattr(sessions_mod, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")
    sid = "33333333-3333-3333-3333-333333333333"
    lines = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Which one?"}]}},
        {"type": "user", "cwd": "/home/u/proj", "message": {"content": "the second one"}},
    ]
    (root / f"{sid}.jsonl").write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    state = next(s.state for s in sessions_mod.discover_sessions() if s.session_id == sid)
    assert state == ""  # user already replied → not waiting


def test_export_markdown(projects_dir):
    _root, ids = projects_dir
    session = next(s for s in discover_sessions() if s.session_id == ids["alpha1"])
    md = export_markdown(session.jsonl_path, "Alpha feature", session.session_id, session.cwd)
    assert md.startswith("# Alpha feature")
    assert f"`{session.session_id}`" in md
    assert "### You\n\nBuild the alpha feature" in md
    assert "### Claude\n\nHello!" in md
    assert "*Used `Bash`*" in md  # tool call noted


def test_parse_details_handles_garbage(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('not json\n{"type": 12}\n[]\n', encoding="utf-8")
    details = parse_details(bad)
    assert details.user_messages == 0
    assert details.models == []


def test_discover_handles_missing_dir(monkeypatch, tmp_path):
    import agent_tablet.sessions as sessions_mod

    monkeypatch.setattr(sessions_mod, "CLAUDE_PROJECTS_DIR", tmp_path / "nope")
    assert discover_sessions() == []


# -- Claude's own name (plan 01 B2) ----------------------------------------------------------


def _title_line(kind: str, value: str) -> dict:
    key = {"custom-title": "customTitle", "ai-title": "aiTitle"}[kind]
    return {"type": kind, key: value, "sessionId": "s"}


def _write_lines(path, entries) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


@pytest.mark.parametrize(
    "position",
    [pytest.param(2, id="line-3"), pytest.param(4_999, id="line-5000")],
)
def test_claudes_name_is_found_on_any_line(tmp_path, position):
    filler = make_transcript_lines("/proj", "hello") * (position // 5 + 1)
    entries = [*filler[:position], _title_line("custom-title", "lm-plan-200"), *filler[position:]]
    path = tmp_path / "t.jsonl"
    _write_lines(path, entries)
    assert read_titles(path) == ("lm-plan-200", "")


def test_the_last_rename_wins(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_lines(
        path,
        [
            _title_line("custom-title", "first"),
            *make_transcript_lines("/p", "x"),
            _title_line("custom-title", "second"),
        ],
    )
    assert read_titles(path)[0] == "second"


def test_a_session_with_no_name_reads_empty_and_keeps_its_ai_title(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_lines(path, [*make_transcript_lines("/p", "x"), _title_line("ai-title", "Fix the bug")])
    assert read_titles(path) == ("", "Fix the bug")


def test_a_name_appended_later_is_read_without_rereading_the_start(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_lines(path, [_title_line("custom-title", "old"), *make_transcript_lines("/p", "x")])
    assert read_titles(path)[0] == "old"
    assert TITLE_SCANS[path].offset == path.stat().st_size
    # The start is replaced by bytes of the same length that hold no name: a reader that started
    # over would lose "old"; one that resumes from its offset never sees them.
    data = path.read_bytes()
    first_line_end = data.index(b"\n")
    path.write_bytes(b" " * first_line_end + data[first_line_end:])
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "more"}}) + "\n")
    assert read_titles(path)[0] == "old"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_title_line("custom-title", "new")) + "\n")
    assert read_titles(path)[0] == "new"
    assert TITLE_SCANS[path].offset == path.stat().st_size


def test_a_line_still_being_written_is_read_once_it_is_complete(tmp_path):
    path = tmp_path / "t.jsonl"
    whole = json.dumps(_title_line("custom-title", "late")) + "\n"
    path.write_text(whole[:10], encoding="utf-8")
    assert read_titles(path)[0] == ""
    path.write_text(whole, encoding="utf-8")
    assert read_titles(path)[0] == "late"


def test_a_file_that_shrank_is_read_again_from_the_start(tmp_path):
    path = tmp_path / "t.jsonl"
    _write_lines(path, [*make_transcript_lines("/p", "x"), _title_line("custom-title", "long-name")])
    read_titles(path)
    _write_lines(path, [_title_line("custom-title", "b")])
    assert read_titles(path)[0] == "b"


@pytest.mark.parametrize(
    ("claude_name", "app_name", "ai_title", "preview", "expected"),
    [
        pytest.param("lm-plan", "mine", "AI", "first", "lm-plan", id="claude-wins-over-the-app"),
        pytest.param("", "mine", "AI", "first", "mine", id="app-name-only-without-claudes"),
        pytest.param("", "", "AI", "first", "AI", id="then-claudes-own-title"),
        pytest.param("", "", "", "first", "first", id="then-the-first-message"),
        pytest.param("", "", "", "", "12345678", id="then-the-id"),
    ],
)
def test_a_sessions_title_follows_claudes_name_first(
    tmp_path, claude_name, app_name, ai_title, preview, expected
):
    session = Session(
        session_id="12345678-aaaa",
        jsonl_path=tmp_path / "x.jsonl",
        cwd="/p",
        preview=preview,
        mtime=0.0,
        claude_name=claude_name,
        ai_title=ai_title,
    )
    assert session_title(session, app_name or None) == expected


def test_discovery_carries_claudes_name(projects_dir):
    root, ids = projects_dir
    path = next(root.glob(f"*/{ids['beta1']}.jsonl"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n" + json.dumps(_title_line("custom-title", "beta-docs")) + "\n")
    by_id = {s.session_id: s for s in discover_sessions()}
    assert by_id[ids["beta1"]].claude_name == "beta-docs"
    assert by_id[ids["alpha1"]].claude_name == ""
