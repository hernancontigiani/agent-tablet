import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agent_tablet import context, contextring

T0 = datetime(2026, 11, 6, 23, 30, tzinfo=UTC)


def _transcript(path: Path, at: datetime, input_tokens: int, cache_write: int, cache_read: int) -> Path:
    lines = [
        {"type": "user", "timestamp": (at - timedelta(seconds=30)).isoformat(), "message": {"content": "go"}},
        {
            "type": "assistant",
            "timestamp": at.isoformat(),
            "message": {
                "model": "claude-opus-5-5",
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": 400,
                    "cache_creation_input_tokens": cache_write,
                    "cache_read_input_tokens": cache_read,
                },
            },
        },
        {"type": "user", "timestamp": (at + timedelta(seconds=1)).isoformat(), "message": {"content": []}},
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


def _session_file(cache: Path, session_id: str, percentage, window: int, at: datetime) -> None:
    sessions = cache / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = dict(dict.fromkeys(context.SESSION_FIELDS))
    record.update(session_id=session_id, percentage=percentage, window=window, updated_at=at.isoformat())
    (sessions / f"{session_id}.json").write_text(json.dumps(record), encoding="utf-8")


def test_a_statusline_file_becomes_an_exact_reading(tmp_path):
    transcript = _transcript(tmp_path / "s.jsonl", T0, 10, 0, 50_000)
    _session_file(tmp_path, "s", 62.0, 200_000, T0 + timedelta(seconds=2))
    reading = context.reading_for("s", transcript, tmp_path)
    assert reading == context.ContextReading(62.0, 200_000, "statusline")


def test_no_file_gives_an_estimate_over_200k(tmp_path):
    transcript = _transcript(tmp_path / "s.jsonl", T0, 1_000, 9_000, 40_000)  # 50k in the window
    reading = context.reading_for("s", transcript, tmp_path)
    assert reading == context.ContextReading(25.0, 200_000, "estimate")


def test_an_estimate_uses_the_last_reported_window(tmp_path):
    transcript = _transcript(tmp_path / "s.jsonl", T0, 0, 0, 250_000)
    _session_file(tmp_path, "s", None, 1_000_000, T0 - timedelta(minutes=5))  # reported early, no %
    reading = context.reading_for("s", transcript, tmp_path)
    assert reading == context.ContextReading(25.0, 1_000_000, "estimate")


def test_a_file_older_than_the_transcript_falls_back_to_the_estimate(tmp_path):
    transcript = _transcript(tmp_path / "s.jsonl", T0, 0, 0, 120_000)
    _session_file(tmp_path, "s", 10.0, 200_000, T0 - timedelta(hours=1))  # the session moved on since
    reading = context.reading_for("s", transcript, tmp_path)
    assert reading == context.ContextReading(60.0, 200_000, "estimate")


def test_nothing_to_go_on_gives_no_reading(tmp_path):
    assert context.reading_for("s", tmp_path / "missing.jsonl", tmp_path) is None


def test_only_the_last_assistant_message_counts_even_in_a_long_transcript(tmp_path):
    path = tmp_path / "long.jsonl"
    filler = json.dumps({"type": "user", "timestamp": T0.isoformat(), "message": {"content": "x" * 900}})
    with path.open("w", encoding="utf-8") as out:
        for minutes in range(3000):  # ~3 MB, past the tail the reader looks at first
            at = T0 + timedelta(minutes=minutes)
            usage = {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": minutes}
            out.write(
                json.dumps({"type": "assistant", "timestamp": at.isoformat(), "message": {"usage": usage}})
            )
            out.write("\n" + filler + "\n")
    found = context.last_assistant_usage(path)
    assert found is not None
    tokens, at = found
    assert tokens == 2999
    assert at == T0 + timedelta(minutes=2999)


@pytest.mark.parametrize(
    ("percentage", "level"),
    [(0, "ok"), (59.9, "ok"), (60, "warn"), (79.9, "warn"), (80, "full"), (100, "full")],
)
def test_the_level_changes_at_60_and_80(percentage, level):
    assert contextring.level(percentage) == level


def test_the_tooltip_marks_an_estimate():
    exact = context.ContextReading(62.0, 200_000, "statusline")
    estimate = context.ContextReading(25.0, 1_000_000, "estimate")
    assert contextring.tooltip(exact) == "62% of 200k"
    assert contextring.tooltip(estimate) == "~25% of 1M (estimate)"


def test_a_reported_window_of_zero_falls_back_to_200k(tmp_path):
    transcript = _transcript(tmp_path / "s.jsonl", T0, 0, 0, 100_000)
    _session_file(tmp_path, "s", None, 0, T0 - timedelta(minutes=1))
    assert context.reading_for("s", transcript, tmp_path) == context.ContextReading(50.0, 200_000, "estimate")
