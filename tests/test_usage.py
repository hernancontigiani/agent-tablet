import json
import os
from pathlib import Path

import pytest

from agent_tablet import usage

DATA = Path(__file__).parent / "data" / "usage"
SESSION = "11111111-1111-4111-8111-111111111111"


def _assistant(
    message_id, request_id, output, cache_read=0, *, sidechain=False, model="claude-opus-5-5", **extra
):
    return {
        "type": "assistant",
        "timestamp": "2026-11-06T12:00:00Z",
        "requestId": request_id,
        "isSidechain": sidechain,
        "message": {
            "id": message_id,
            "model": model,
            "usage": {
                "input_tokens": 1,
                "output_tokens": output,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": cache_read,
            },
        },
        **extra,
    }


def _transcript(
    projects: Path, lines: list[dict], session: str = SESSION, folder: str = "-home-demo-app"
) -> Path:
    path = projects / folder / f"{session}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        for line in lines:
            out.write(json.dumps(line) + "\n")
    return path


@pytest.fixture
def cache(tmp_path):
    return usage.UsageCache(tmp_path / "usage.sqlite")


def test_a_response_logged_three_times_counts_once(tmp_path, cache):
    projects = tmp_path / "projects"
    copy = _assistant("msg_a", "req_a", 100, 5000)
    _transcript(projects, [copy, copy, copy])
    cache.ingest(projects)
    assert cache.tokens(SESSION) == usage.Tokens(
        input=1, output=100, cache_write=0, cache_write_1h=0, cache_read=5000
    )


def test_a_real_duplicated_response_counts_once(tmp_path, cache):
    """Recorded from a real transcript (content scrubbed): one response written three times."""
    projects = tmp_path / "projects"
    folder = projects / "-home-demo-app"
    folder.mkdir(parents=True)
    (folder / "00000000-0000-4000-8000-000000000001.jsonl").write_text(
        (DATA / "duplicated.jsonl").read_text(encoding="utf-8"), encoding="utf-8"
    )
    cache.ingest(projects)
    tokens = cache.tokens("00000000-0000-4000-8000-000000000001")
    assert tokens == usage.Tokens(
        input=2, output=3343, cache_write=3189, cache_write_1h=3189, cache_read=303323
    )


def test_the_non_sidechain_copy_wins(tmp_path, cache):
    projects = tmp_path / "projects"
    _transcript(projects, [_assistant("msg_b", "req_b", 900, sidechain=True)], session="sub")
    _transcript(projects, [_assistant("msg_b", "req_b", 100)])
    cache.ingest(projects)
    assert cache.tokens(SESSION).output == 100
    assert cache.tokens("sub").output == 0


def test_a_subagent_transcript_adds_to_its_parent(tmp_path, cache):
    projects = tmp_path / "projects"
    _transcript(projects, [_assistant("msg_p", "req_p", 100)])
    subagent = projects / "-home-demo-app" / SESSION / "subagents" / "agent-1.jsonl"
    subagent.parent.mkdir(parents=True)
    subagent.write_text(json.dumps(_assistant("msg_s", "req_s", 40, sidechain=True)) + "\n", encoding="utf-8")
    cache.ingest(projects)
    assert cache.tokens(SESSION).output == 140


def test_synthetic_and_api_errors_are_not_counted(tmp_path, cache):
    projects = tmp_path / "projects"
    _transcript(
        projects,
        [
            _assistant("msg_1", "req_1", 100),
            _assistant("msg_2", "req_2", 500, model="<synthetic>"),
            _assistant("msg_3", "req_3", 700, isApiErrorMessage=True),
            _assistant("msg_4", "req_4", 0, 9000),  # only cache tokens: still counted
        ],
    )
    cache.ingest(projects)
    assert cache.tokens(SESSION) == usage.Tokens(
        input=2, output=100, cache_write=0, cache_write_1h=0, cache_read=9000
    )


def test_a_second_pass_reads_only_what_was_appended(tmp_path, cache):
    projects = tmp_path / "projects"
    path = _transcript(projects, [_assistant("msg_1", "req_1", 100)])
    first = cache.ingest(projects)
    assert first == path.stat().st_size
    assert cache.ingest(projects) == 0
    _transcript(projects, [_assistant("msg_2", "req_2", 50)])
    appended = cache.ingest(projects)
    assert appended == path.stat().st_size - first
    fresh = usage.UsageCache(tmp_path / "fresh.sqlite")
    fresh.ingest(projects)
    assert cache.tokens(SESSION) == fresh.tokens(SESSION)


def test_a_line_still_being_written_is_read_next_time(tmp_path, cache):
    projects = tmp_path / "projects"
    path = _transcript(projects, [_assistant("msg_1", "req_1", 100)])
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(_assistant("msg_2", "req_2", 50))[:40])  # no newline yet
    cache.ingest(projects)
    assert cache.tokens(SESSION).output == 100
    rest = json.dumps(_assistant("msg_2", "req_2", 50))[40:]
    with path.open("a", encoding="utf-8") as out:
        out.write(rest + "\n")
    cache.ingest(projects)
    assert cache.tokens(SESSION).output == 150


def test_a_rewritten_transcript_is_read_again(tmp_path, cache):
    projects = tmp_path / "projects"
    path = _transcript(projects, [_assistant("msg_1", "req_1", 100), _assistant("msg_2", "req_2", 100)])
    cache.ingest(projects)
    path.unlink()
    _transcript(projects, [_assistant("msg_3", "req_3", 7)])  # a new, shorter file at the same path
    assert cache.ingest(projects) == path.stat().st_size
    assert cache.tokens(SESSION).output >= 7


def test_a_new_schema_version_rebuilds_the_cache(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    _transcript(projects, [_assistant("msg_1", "req_1", 100)])
    usage.UsageCache(tmp_path / "u.sqlite").ingest(projects)
    monkeypatch.setattr(usage, "SCHEMA_VERSION", usage.SCHEMA_VERSION + 1)
    rebuilt = usage.UsageCache(tmp_path / "u.sqlite")
    assert rebuilt.tokens(SESSION) == usage.Tokens()  # empty until it reads again
    assert rebuilt.ingest(projects) > 0
    assert rebuilt.tokens(SESSION).output == 100


def test_the_cache_lives_under_the_cache_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert usage.cache_path() == tmp_path / "agent-tablet" / "usage.sqlite"
    assert os.path.commonpath([usage.cache_path(), tmp_path]) == str(tmp_path)


def test_a_sidechain_replay_of_a_parent_response_is_not_counted(tmp_path, cache):
    """A sidechain may log a parent's response again under another request id (ccusage #913)."""
    projects = tmp_path / "projects"
    _transcript(projects, [_assistant("msg_p", "req_parent", 100, 50_000)])
    subagent = projects / "-home-demo-app" / SESSION / "subagents" / "agent-1.jsonl"
    subagent.parent.mkdir(parents=True)
    replay = _assistant("msg_p", "req_replay", 100, 50_000, sidechain=True)
    own = _assistant("msg_own", "req_own", 30, sidechain=True)
    subagent.write_text(json.dumps(replay) + "\n" + json.dumps(own) + "\n", encoding="utf-8")
    cache.ingest(projects)
    assert cache.tokens(SESSION).output == 130  # the parent's 100 once, the subagent's own 30


# -- execution time --------------------------------------------------------------------------

from datetime import UTC, datetime, timedelta

T0 = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)


def _at(seconds: float) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _turn(seconds: float, origin: str = "human") -> dict:
    return {"type": "user", "timestamp": _at(seconds), "turnOrigin": origin, "message": {"content": "go"}}


def _reply(seconds: float, message_id: str, tool: tuple[str, str] | None = None) -> dict:
    content = [{"type": "tool_use", "id": tool[0], "name": tool[1], "input": {}}] if tool else []
    entry = _assistant(message_id, f"req-{message_id}", 10)
    entry["timestamp"] = _at(seconds)
    entry["message"]["content"] = content
    return entry


def _result(seconds: float, tool_id: str, source: str = "config") -> dict:
    return {
        "type": "user",
        "timestamp": _at(seconds),
        "toolUseResult": {"ok": True},
        "permissionDecision": {"decision": "accept", "source": source},
        "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "x"}]},
    }


def _times(tmp_path, lines, *, session=SESSION):
    projects = tmp_path / "projects"
    _transcript(projects, lines, session=session)
    cache = usage.UsageCache(tmp_path / "t.sqlite")
    cache.ingest(projects)
    return cache.time(session)


def test_execution_is_the_sum_of_gaps_between_activities(tmp_path):
    t = _times(tmp_path, [_turn(0), _reply(30, "a", ("t1", "Bash")), _result(90, "t1"), _reply(100, "b")])
    assert t.execution == {"human": 100.0}
    assert t.blocked == 0.0


def test_a_gap_over_2_hours_is_idle(tmp_path):
    within = 2 * 3600 - 1
    beyond = 2 * 3600 + 1
    t = _times(tmp_path, [_turn(0), _reply(within, "a"), _reply(within + beyond, "b")])
    assert t.execution == {"human": float(within)}


def test_a_41_minute_tool_counts_whole(tmp_path):
    lines = [_turn(0), _reply(10, "a", ("t1", "Bash")), _result(10 + 41 * 60, "t1"), _reply(2480, "b")]
    t = _times(tmp_path, lines)
    assert t.execution == {"human": 2480.0}


def test_a_permission_wait_is_blocked_not_execution(tmp_path):
    lines = [
        _turn(0),
        _reply(10, "a", ("t1", "Bash")),
        _result(310, "t1", "user_temporary"),
        _reply(320, "b"),
    ]
    t = _times(tmp_path, lines)
    assert t.blocked == 300.0
    assert t.execution == {"human": 20.0}


def test_an_ask_user_question_is_blocked(tmp_path):
    lines = [_turn(0), _reply(10, "a", ("q1", "AskUserQuestion")), _result(1210, "q1"), _reply(1215, "b")]
    t = _times(tmp_path, lines)
    assert t.blocked == 1200.0  # a 20-minute wait on the human is blocked, not idle
    assert t.execution == {"human": 15.0}


def test_a_turn_is_filed_under_who_started_it(tmp_path):
    lines = [
        _turn(0, "human"),
        _reply(60, "a"),
        _turn(100, "peer"),
        _reply(130, "b"),
        _turn(200, "task_notification"),
    ]
    lines.append(_reply(210, "c"))
    t = _times(tmp_path, lines)
    assert t.execution == {"human": 60.0, "peer": 30.0, "task_notification": 10.0}


def test_a_resumed_session_does_not_stretch_the_old_turn(tmp_path):
    day = 24 * 3600
    meta = {"type": "user", "timestamp": _at(day), "isMeta": True, "message": {"content": "<local-command>"}}
    t = _times(tmp_path, [_turn(0), _reply(60, "a"), meta, _turn(day + 5), _reply(day + 65, "b")])
    assert t.execution == {"human": 120.0}


def test_a_turn_across_midnight_is_split_at_local_midnight(tmp_path, monkeypatch):
    monkeypatch.setenv("TZ", "America/Argentina/Buenos_Aires")  # UTC−3
    __import__("time").tzset()
    try:
        midnight_utc = datetime(2026, 11, 7, 3, 0, tzinfo=UTC)  # 00:00 local
        start = (midnight_utc - T0).total_seconds() - 120
        lines = [_turn(start), _reply(start + 60, "a"), _reply(start + 180, "b")]
        projects = tmp_path / "projects"
        _transcript(projects, lines)
        cache = usage.UsageCache(tmp_path / "t.sqlite")
        cache.ingest(projects)
        local = midnight_utc.astimezone()
        assert cache.time(SESSION, end=local).execution == {"human": 120.0}
        assert cache.time(SESSION, start=local).execution == {"human": 60.0}
    finally:
        monkeypatch.delenv("TZ")
        __import__("time").tzset()


def test_a_turn_read_in_two_passes_counts_as_in_one(tmp_path):
    projects = tmp_path / "projects"
    cache = usage.UsageCache(tmp_path / "t.sqlite")
    _transcript(projects, [_turn(0), _reply(10, "a", ("t1", "Bash"))])
    cache.ingest(projects)
    _transcript(projects, [_result(70, "t1", "user_temporary"), _reply(80, "b")])
    cache.ingest(projects)
    t = cache.time(SESSION)
    assert t.blocked == 60.0
    assert t.execution == {"human": 20.0}


def test_a_rewritten_transcript_does_not_count_its_old_time(tmp_path):
    projects = tmp_path / "projects"
    cache = usage.UsageCache(tmp_path / "t.sqlite")
    path = _transcript(projects, [_turn(0), _reply(100, "a"), _reply(200, "b")])
    cache.ingest(projects)
    path.unlink()
    _transcript(projects, [_turn(0), _reply(5, "c")])
    cache.ingest(projects)
    assert cache.time(SESSION).execution == {"human": 5.0}


# -- the report ------------------------------------------------------------------------------


def _usage_line(path: Path, session: str, seconds: float, cost: float, five=None, seven=None) -> None:
    line = {
        "at": _at(seconds),
        "session_id": session,
        "cost_usd": cost,
        "five_hour_pct": five,
        "seven_day_pct": seven,
    }
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")


def _two_sessions(tmp_path):
    projects = tmp_path / "projects"
    _transcript(projects, [_turn(0), _reply(60, "a"), {"type": "custom-title", "customTitle": "lm-plan-1"}])
    _transcript(projects, [_turn(0, "peer"), _reply(30, "b")], session="22222222-2222-4222-8222-222222222222")
    cache = usage.UsageCache(tmp_path / "t.sqlite")
    cache.ingest(projects)
    return cache


def test_a_node_is_the_sum_of_its_children(tmp_path):
    cache = _two_sessions(tmp_path)
    memberships = {SESSION: "Core", "22222222-2222-4222-8222-222222222222": "Core"}
    report = usage.report(
        cache, T0 - timedelta(hours=1), T0 + timedelta(hours=1), memberships, tmp_path / "none"
    )
    (project,) = report.nodes
    assert project.label == "Core"
    (category,) = project.children
    assert category.label == usage.NO_CATEGORY
    sessions = category.children
    assert len(sessions) == 2
    for parent in (project, category):
        kids = parent.children
        assert parent.tokens.total == sum(k.tokens.total for k in kids)
        assert parent.total_execution == pytest.approx(sum(k.total_execution for k in kids))
    assert {s.label for s in sessions} == {"lm-plan-1", "22222222"}
    assert project.execution == {"human": 60.0, "peer": 30.0}


def test_a_session_in_no_project_is_reported_under_no_project(tmp_path):
    cache = _two_sessions(tmp_path)
    report = usage.report(
        cache, T0 - timedelta(hours=1), T0 + timedelta(hours=1), {SESSION: "Core"}, tmp_path / "none"
    )
    assert [node.label for node in report.nodes] == ["Core", usage.NO_PROJECT]


def test_the_7_day_period_ends_today_at_local_midnight(monkeypatch):
    monkeypatch.setenv("TZ", "America/Argentina/Buenos_Aires")
    __import__("time").tzset()
    try:
        now = datetime(2026, 11, 6, 23, 30).astimezone()
        start, end = usage.period_bounds("7d", now)
        assert (start.date(), start.hour) == (datetime(2026, 10, 31).date(), 0)
        assert (end.date(), end.hour) == (datetime(2026, 11, 7).date(), 0)
        assert usage.period_bounds("today", now)[0].date() == now.date()
    finally:
        monkeypatch.delenv("TZ")
        __import__("time").tzset()


def test_the_estimate_prices_each_entry_and_says_when_a_model_is_unknown(tmp_path):
    projects = tmp_path / "projects"
    _transcript(
        projects, [_assistant("m1", "r1", 1_000_000), _assistant("m2", "r2", 1, model="claude-imaginary-9")]
    )
    cache = usage.UsageCache(tmp_path / "t.sqlite")
    cache.ingest(projects)
    cost, all_priced = cache.estimated_cost(SESSION)
    assert cost == pytest.approx(20 + 4 / 1_000_000)  # opus 5.5 output $20/M, input $4/M
    assert not all_priced


def test_the_statusline_cost_replaces_the_estimate_for_its_session(tmp_path):
    cache = _two_sessions(tmp_path)
    usage_file = tmp_path / "usage.jsonl"
    _usage_line(usage_file, SESSION, 10, 0.40)
    _usage_line(usage_file, SESSION, 50, 1.00, five=41.0, seven=12.5)
    report = usage.report(cache, T0 - timedelta(hours=1), T0 + timedelta(hours=1), {}, usage_file)
    session = next(s for s in report.nodes[0].children[0].children if s.label == "lm-plan-1")
    assert (session.cost, session.cost_exact) == (pytest.approx(1.00), True)
    assert report.limits == (41.0, 12.5)


def test_a_clear_does_not_lower_the_statusline_cost(tmp_path):
    usage_file = tmp_path / "usage.jsonl"
    for seconds, cost in [(0, 0.5), (10, 2.0), (20, 0.1), (30, 0.7)]:  # /clear between 2.0 and 0.1
        _usage_line(usage_file, SESSION, seconds, cost)
    costs = usage.statusline_costs(usage_file, T0 - timedelta(hours=1), T0 + timedelta(hours=1))
    assert costs[SESSION] == pytest.approx(2.0 + 0.7)


def test_the_cli_and_the_report_agree(tmp_path, capsys):
    cache = _two_sessions(tmp_path)
    start, end = T0 - timedelta(hours=1), T0 + timedelta(hours=1)
    expected = usage.report(cache, start, end, {}, tmp_path / "none").to_json()
    usage.print_report(usage.report(cache, start, end, {}, tmp_path / "none"), as_json=True)
    assert json.loads(capsys.readouterr().out) == expected


@pytest.mark.parametrize(("seconds", "shown"), [(90, "2m"), (3599, "60m"), (3600, "1.0h"), (5400, "1.5h")])
def test_a_duration_under_an_hour_is_shown_in_minutes(seconds, shown):
    assert usage.duration(seconds) == shown
