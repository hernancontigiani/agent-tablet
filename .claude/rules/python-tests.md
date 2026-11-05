---
paths:
  - "tests/**/*.py"
---

# Writing a Python test

A checklist, not an explanation. If it contradicts `CLAUDE.md`, `CLAUDE.md` wins and this file is
out of date.

## Before writing

- **Find the closest existing test and extend it** — a new `pytest.param` is cheaper than a new
  function, and a new function is cheaper than a new file. A case that needs a sentence to explain
  why it exists gets it as the param's `id` or a comment on it.
- **pytest only**: fixtures, `tmp_path`, `monkeypatch`, `pytest.mark.parametrize`. No assertion
  library; a failure message says what was expected and what arrived.
- **Name the test as the sentence it proves** (`test_claude_name_wins_over_the_app_name`), not
  after the function it calls. When it fails, the name is the bug report.

## The data

- **Data is built by the shared factories in `tests/conftest.py`** (`make_transcript_lines`, and
  whatever is added next to it). A helper copied into a test file is the next one to drift; what a
  factory lacks is added there, and **whoever touches a file with its own copy migrates it** in the
  same change.
- **Real files in `tmp_path`**: a transcript is a real `.jsonl`, the state is a real `state.json`.
  A fake is only for what a test cannot run (a live `claude` process, D-Bus, a display), it lives in
  one place, and it is driven from recorded output in `tests/data/`.
- **Recorded output from a real session is scrubbed before it is committed**: a transcript carries
  prompts, paths and code.

## The environment

- **Never read the developer's machine**: not `~/.claude`, not `~/.claude.json`, not
  `~/.config`, not a running instance of the app. **The existing modules resolve those paths at
  import**, so setting `HOME` or `XDG_CONFIG_HOME` inside a test changes nothing: use the
  `projects_dir`, `cursor_projects_dir` and `app_state` fixtures, which patch the module constants.
  New code resolves paths when called, so its tests can point it at `tmp_path` directly.
- **No GTK main loop and no display** in a unit test. Logic that a widget calls lives in a function
  that can be tested without one; a test that truly needs a display skips with the reason and how to
  run it.
- **No `datetime.now()`, `time.time()` or absolute date that feeds a path reading the real clock.**
  Inject the time and build the scenario from a fixed instant with offsets; a fixed date the code
  compares against "now" turns red the day it passes. Cover the edges: midnight, a session spanning
  two days, `TZ` other than the developer's.

## What the test asserts

- **If it discovers what it compares** (files, transcript lines, registered actions), **it first
  asserts a floor** of what it found — a loop over nothing passes.
- **If it asserts that something is not written** (into a transcript, into `~/.claude`), **it
  asserts by invariance** — the file's bytes are identical before and after — never by searching for
  a substring.
- **Seen red once.** Break the code under test from the test (`monkeypatch`) or invert the
  assertion, watch it fail, then put it back. Never by editing shared code another session may be
  reading.
- **The suite runs in parallel** (`-n auto`). A test that depends on another having run first, or on
  module state left behind, is broken even when it passes alone.

## When done

- The file alone first (`uv run pytest tests/test_x.py`), then `make ci`.
- `ruff format` and `--fix` only on your own files: `make fmt FILES="..."`.
