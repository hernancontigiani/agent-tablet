# Plan 02 — Toolchain baseline: Python 3.12, one ruff standard, pyright

> **Status:** stub, 2026-11-05 — needs `/design-plan` (no execution blocks yet).
>
> **Exit:** the gate's new steps and the ruff rule set → `CLAUDE.md` ("Local CI", "Python") and
> `pyproject.toml`, whose every `ignore` carries its reason; what is deliberately left unchecked →
> `docs/NOT_BUILT_YET.md`; the rest → `git log`.
>
> Comes from the setup of 2026-11-05: once the fork stopped tracking upstream, nothing prevents
> holding the whole tree to one standard.

## Goal

The whole tree under the same rules the additions will be written with, and `make ci` enforcing
them, before B2 of plan 01 starts writing new modules.

## What exists (measured 2026-11-05 at `07f72bd`, 37 Python files, ~6,900 lines in the package)

- `requires-python = ">=3.10"`, ruff `target-version = "py310"`, `line-length = 110`, select
  `E,F,W,I,UP,B`, `ignore = ["E402"]` (with its reason). `ruff check` is clean.
- `ruff format --check`: 25 files would be reformatted, 12 already are.
- The target rule set (`E,W,F,I,UP,B,C4,SIM,RUF,T20`) over the tree: 65 findings, 27 of them unused
  `noqa` (RUF100).
- `pyright` basic over the tree, with `pygobject-stubs`: 108 errors, 90 warnings.
- No `print`, no `logging`, one `datetime.now()`-style call in the package.
- Paths are resolved at import (`state.py:14`, `sessions.py:22-24`); tests patch module constants
  through the `projects_dir` / `app_state` fixtures.

## Decided

- Python 3.12 (`requires-python`, ruff `target-version`, `debian/control`), 2026-11-05.
- pyright basic joins the gate, with `pygobject-stubs` from the dev group, 2026-11-05.

## To design

- **Order of the blocks** so each leaves the tree green: format alone first (a pure-whitespace
  change, easy to review), then the 3.12 bump and its `UP` rewrites, then the stricter rule set,
  then pyright.
- **Which of the 108 pyright errors are real bugs** versus missing stubs: a real one is a finding
  for the human, not something fixed silently inside a typing block.
- Whether the test guards from `CLAUDE.md` become tests now: an AST test forbidding
  `datetime.now()` / `time.time()` in logic, and an autouse fixture that points `HOME` and the XDG
  variables at `tmp_path` so no test can read the human's files.
- **A whole-suite clock shift** (`time-machine` in the dev group plus a small `tests/clock_plugin.py`):
  with `AT_TEST_CLOCK_AT=<ISO instant>` set, Python's clock is moved for the whole run, so
  `AT_TEST_CLOCK_AT=<today 23:30 local> TZ=UTC uv run pytest -n auto` finds the tests that only pass
  away from midnight. It earns its place once B4–B6 add timers and cost windows; decide whether it
  lands here or with B4. It does not replace injecting the clock: it finds where someone forgot.
- **Coverage** (`pytest-cov`) as a report, never as a threshold in the gate: a number to look at
  when deciding what a block must test, not a target to game.
- **xdist stays out of `addopts`**: a single file while writing a test runs without workers; the
  gate passes `-n auto`. Record it in `CLAUDE.md` with that reason.
- Whether B1's package rename lands before or after the format pass (both touch every file).
  B1 goes first (decided order in `plans/00-STATUS.md`), so the format pass runs on the renamed tree.

## Out of scope

Rewriting import-time path resolution in existing modules (the rule applies to new code); new
features.
