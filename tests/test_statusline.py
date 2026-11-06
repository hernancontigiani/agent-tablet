import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_tablet import context_fields

SCRIPT = Path(__file__).resolve().parent.parent / "agent_tablet" / "statusline.py"
DATA = Path(__file__).parent / "data" / "statusline"


def _run(stdin: str, cache: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "XDG_CACHE_HOME": str(cache)}
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env, timeout=20
    )


def _payload(name: str) -> str:
    return (DATA / f"{name}.json").read_text(encoding="utf-8")


def _usage_lines(cache: Path) -> list[dict]:
    path = cache / "agent-tablet" / "usage.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_full_payload_writes_the_session_file_and_one_usage_line(tmp_path):
    result = _run(_payload("full"), tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "lm-plan-200 · 62% · $1.23"

    session = json.loads(
        (tmp_path / "agent-tablet" / "sessions" / "5f1c2a90-0000-4000-8000-000000000001.json").read_text()
    )
    assert session["percentage"] == 62.0
    assert session["window"] == 200000
    assert session["session_name"] == "lm-plan-200"

    (line,) = _usage_lines(tmp_path)
    assert line["session_id"] == "5f1c2a90-0000-4000-8000-000000000001"
    assert line["cost_usd"] == 1.2345
    assert (line["lines_added"], line["lines_removed"]) == (120, 30)
    assert (line["five_hour_pct"], line["seven_day_pct"]) == (41.0, 12.5)


def test_an_early_payload_with_null_percentage_still_writes_and_prints(tmp_path):
    result = _run(_payload("early"), tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "5f1c2a90 · $0.00"
    session = json.loads(
        (tmp_path / "agent-tablet" / "sessions" / "5f1c2a90-0000-4000-8000-000000000002.json").read_text()
    )
    assert session["percentage"] is None
    assert session["window"] == 200000


@pytest.mark.parametrize("stdin", ["not json at all", "[1, 2, 3]", ""], ids=["garbage", "a-list", "empty"])
def test_a_payload_that_is_not_json_prints_a_fallback_and_exits_zero(tmp_path, stdin):
    result = _run(stdin, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "agent-tablet"
    assert not (tmp_path / "agent-tablet" / "sessions").exists()


def test_two_runs_append_two_usage_lines_and_keep_one_session_file(tmp_path):
    _run(_payload("full"), tmp_path)
    _run(_payload("full"), tmp_path)
    assert len(_usage_lines(tmp_path)) == 2
    assert len(list((tmp_path / "agent-tablet" / "sessions").iterdir())) == 1


def test_the_script_writes_every_field_the_app_reads(tmp_path):
    """The script and the app's context model meet in this file: one vocabulary, on both sides."""
    _run(_payload("full"), tmp_path)
    (written,) = (tmp_path / "agent-tablet" / "sessions").iterdir()
    assert len(context_fields.SESSION_FIELDS) >= 6
    assert set(json.loads(written.read_text())) == set(context_fields.SESSION_FIELDS)


def _run_with_chain(
    stdin: str, cache: Path, config: Path, command: str | None
) -> subprocess.CompletedProcess:
    chain = config / "agent-tablet" / "chained-statusline.json"
    chain.parent.mkdir(parents=True, exist_ok=True)
    chain.write_text(json.dumps({"command": command}), encoding="utf-8")
    env = {**os.environ, "XDG_CACHE_HOME": str(cache), "XDG_CONFIG_HOME": str(config)}
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env, timeout=20
    )


def test_the_human_s_own_bar_is_shown_and_the_app_still_records(tmp_path):
    """Their bar does not change; the app only adds what it records on the side."""
    command = 'read payload; echo "theirs: $(echo "$payload" | head -c 1)"'
    result = _run_with_chain(
        _payload("full").replace("\n", " "), tmp_path / "cache", tmp_path / "config", command
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "theirs: {"
    assert (tmp_path / "cache" / "agent-tablet" / "sessions").exists()


@pytest.mark.parametrize("command", ["exit 3", "true"], ids=["fails", "prints-nothing"])
def test_a_chained_bar_that_fails_or_prints_nothing_falls_back_to_the_app_s(tmp_path, command):
    result = _run_with_chain(_payload("full"), tmp_path / "cache", tmp_path / "config", command)
    assert result.returncode == 0
    assert result.stdout.strip() == "lm-plan-200 · 62% · $1.23"
