# Plan 02 — Toolchain baseline: Python 3.12, one ruff standard, pyright at zero

> **Status:** written 2026-11-06, ready to execute. Designed from the stub of 2026-11-05 and
> measurements taken on 2026-11-06 at `af198cc` (below).
>
> **Exit** (where each part goes when executed):
> - The gate's steps, `make test-midnight`, `make coverage` → `CLAUDE.md` "Local CI".
> - "Time is read only through `agent_tablet/clock.py`" and "pyright stays at zero; an ignore names
>   its rule and its reason" → `CLAUDE.md` "Python" (the "Time is injected" bullet is rewritten; its
>   old lines go to `docs/history/root/CLAUDE.md`).
> - The test isolation and the clock shift → `.claude/rules/python-tests.md`.
> - The ruff rule set → `pyproject.toml`, every `ignore` with its reason in a comment.
> - The rest → `git log`.

---

## 1. Goal, and what exists

The whole tree under the rules the additions will be written with, and `make ci` enforcing them,
before plan 01 B2 writes new modules.

**Measured 2026-11-06 at `af198cc`** (`agent_tablet/` 27 files, plus `tests/`, `tools/`,
`scripts/`, `po/`, `docs/history/`):

- `pyproject.toml`: `requires-python = ">=3.10"`, ruff `target-version = "py310"`,
  `line-length = 110`, `select = ["E","F","W","I","UP","B"]`, `ignore = ["E402"]` (with its
  reason). `ruff check` is clean.
- **`ruff format --check`**: 30 files would be reformatted, 23 are already formatted.
- **The target rule set** (`--extend-select C4,SIM,RUF,T20`, which keeps the config's `ignore`):
  27 unused `noqa` (RUF100); 8 `try/except/pass` (SIM105); 5 mutable class attributes (RUF012 —
  GObject's `__gsignals__`); 29 ambiguous Unicode characters (RUF001 — the "…", "·" and en-dashes
  in UI strings, on purpose); 16 `print` (T201 — in `scripts/`, `po/generate.py`, `tools/ui/`,
  `docs/history/nothing_lost.py`, which are command-line tools); a handful more (SIM300, SIM102,
  C416, RUF059, E501).
- **Python 3.12**: `ruff check --select UP --target-version py312` finds nothing to rewrite.
- **pyright basic** (`pythonVersion` 3.12, the project's `.venv`): **131 errors** over
  `agent_tablet/`, `tests/`, `tools/`, and 1 over `scripts/`, `po/`, `docs/history/`; plus 94
  `reportMissingModuleSource` warnings, which only say the stubs' runtime package (the system's
  `gi`) is outside the venv's view. By rule: `reportArgumentType` 50, `reportOptionalMemberAccess`
  48, `reportAttributeAccessIssue` 22, `reportOptionalSubscript` 4, `reportReturnType` 3,
  `reportCallIssue` 2, one each `reportOperatorIssue` and `reportGeneralTypeIssues`. Most in
  `window.py` (32), `sidebar.py` (32), `spaces.py` (18), `terminal.py` (15), `themes.py` (14).
- **The stubs**: `pygobject-stubs` configured for `Gtk4,Gdk4` gives the same count; the VTE stubs
  lack GTK4's `Gtk.Widget` API on `Vte.Terminal` (`add_controller` "unknown") — a gap in the stubs,
  not in the code.
- **Time**: one read of the wall clock in the package, `store.py:30` (`datetime.now()`, the
  "5m ago" of a row).
- `tests/conftest.py` imports nothing of the app at module level; the modules resolve their paths
  at import (`state.py:14`, `sessions.py:22-24`).
- No `pyrightconfig.json` and no `[tool.pyright]` exist.

## 2. Design

**Decided by the human:** Python 3.12; one ruff standard over the whole tree; pyright basic in the
gate (2026-11-05); **every pyright error fixed in this plan, not baselined** and **the clock shift
built now** (2026-11-06). Taken as given: xdist stays out of `addopts`.

1. **Python 3.12 everywhere it is declared**: `requires-python = ">=3.12"`, ruff
   `target-version = "py312"`, `[tool.pyright] pythonVersion = "3.12"`, `debian/control`
   (`python3 (>= 3.12)` in `Depends`), the README's requirements line. *Check*: ruff's UP set is
   in the gate, so a construct 3.12 makes obsolete fails `make ci`.

2. **`ruff format` over the whole tree, once, in a block of its own.** It is the one sanctioned
   exception to "format only your own paths" (`CLAUDE.md`): the block starts only on a clean
   `git status` and the human commits it alone, so the formatting commit carries no logic.
   `make ci` gains `format-check`. *Check*: `git diff --stat` touches only formatting —
   `git diff -w --word-diff` on a sample of files shows no token change — and `make ci` +
   `make ui-check` are green.

3. **The rule set**: `select = ["E","W","F","I","UP","B","C4","SIM","RUF","T20"]`. What is not
   fixed is ignored **with its reason in a comment**:
   - `E402` (kept): `gi.require_version` must precede `gi.repository` imports.
   - `RUF001`/`RUF002`/`RUF003`: the "…", "·" and "–" in user-visible strings are deliberate
     typography, and translators keep them.
   - `T201` per file for the command-line tools: `scripts/*`, `po/generate.py`,
     `tools/ui/{check,serve,session}.py`, `docs/history/nothing_lost.py` — stdout is their
     interface.
   - `UP042` (as lm-app): `StrEnum` is not a drop-in for `(str, Enum)` (`CLAUDE.md`).
   Fixed rather than ignored: unused `noqa` removed; SIM105 → `contextlib.suppress` (same
   behaviour); RUF012 → `ClassVar` annotations on `__gsignals__` (GObject reads the dict
   unchanged); the rest by hand. *Check*: `make ci`; `make ui-check` (the fixes touch
   `sidebar.py`, `spaces.py`, `window.py`).

4. **pyright basic at zero, in the gate.** `[tool.pyright]` in `pyproject.toml`: `basic`, 3.12,
   `venvPath = "."`, `venv = ".venv"`, `include` the six directories,
   `reportMissingModuleSource = false` (reason: the system `gi` is the runtime and the venv sees
   it, pyright does not). Each error is fixed by **the kind it is**:
   - **A gap in the stubs** (the code is right, the stub is wrong — VTE's `Terminal` as a
     `Gtk.Widget`, an `int` where the stub wants a Pango enum that PyGObject accepts): a
     line-scoped `# pyright: ignore[<rule>]` naming the gap, or a typed local
     (`terminal: Gtk.Widget = ...`) where one line covers several calls. Never a file-level
     ignore.
   - **A `None` the code already rules out** (a widget fetched right after it was built, a page
     that exists because the tab exists): narrowed — an early `return` where the old code would
     have done nothing, an `assert x is not None` where the old code would have raised on `None`
     anyway. **Runtime behaviour does not change**; when it would, it is the next kind.
   - **A real defect** (a `None` that can reach a call and crash — the `cwd` passed to
     `_start_new_chat_session` and the path built at `window.py:1095` are the first suspects):
     **not fixed silently.** The executor lists each with the sequence that triggers it and stops
     to ask the human, with options and one recommendation.
   *Check*: `pyright` 0 errors; `make ci` and `make ui-check` green, screenshots looked at.
   **Seen red**: a temporary file with a type error under `agent_tablet/` fails `make ci`.

5. **Time is read only through `agent_tablet/clock.py`** (`now() -> datetime`, `monotonic()`).
   `store.py:30` reads it from there. *Test* `test_nothing_reads_the_clock_outside_clock_py`: walks
   the AST of every module under `agent_tablet/` and fails on a call to `datetime.now`,
   `datetime.today`, `date.today`, `time.time`, `time.monotonic` or `GLib.get_real_time` outside
   `clock.py`; it first asserts it parsed at least 25 modules (a floor: a walk over nothing passes).
   Seen red with a temporary module that calls `datetime.now()`.

6. **No test can read the human's files.** At the top of `tests/conftest.py`, before anything
   imports the app, `HOME`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`,
   `CSM_PROJECTS_DIR` and `CSM_CLAUDE_CONFIG` point into a per-process temporary directory. The
   import-time constants then resolve there. *Test*
   `test_the_suite_never_sees_the_real_home`: `Path.home()` and `state._CONFIG_BASE` are under the
   temporary directory and not under `pwd.getpwuid(os.getuid()).pw_dir`. Seen red by removing the
   override in a temporary copy of the check (monkeypatching `Path.home` back to the real one).

7. **The clock shift for the whole suite** (`time-machine` in the dev group): a pytest plugin,
   `tests/clock_plugin.py`, registered in `conftest.py`; when `AT_TEST_CLOCK_AT=<ISO instant>` is
   set it starts `time_machine.travel(instant, tick=True)` in `pytest_configure` (every xdist
   worker runs it) and stops it in `pytest_unconfigure`. `make test-midnight` runs the suite at
   23:30 local of today with `TZ=UTC`. *Tests*: `test_the_shift_moves_python_s_clock` (with the
   variable, `clock.now()` is within a minute of the instant), `test_no_variable_no_shift`,
   `test_a_malformed_instant_stops_the_run_with_its_value`. The plugin's parsing is a function
   tested directly; the travel itself is checked by running `make test-midnight` once.

8. **Coverage as a report**: `pytest-cov` in the dev group, `make coverage` prints the per-module
   table. Never a threshold in the gate.

**Rejected, and why:**

- **A pyright baseline file** (freeze today's 131, fail only on new ones): the human chose to fix
  them all now (2026-11-06), so the gate's zero is real from day one.
- **`pygobject-stubs` with `config=Gtk4,Gdk4`**: same count as the default; the remaining gaps are
  in the VTE stubs.
- **`extraPaths` to the system `dist-packages`**: pyright then reads the dynamic `gi` instead of
  the stubs and reports 65 unknown attributes.
- **pyright's `standard` mode**: the decision was `basic`.
- **Formatting file by file as each is touched**: two styles side by side for months, and every
  later diff mixes formatting with logic.

## 3. Out of scope

Rewriting import-time path resolution in existing modules (the conftest override makes it safe;
`CLAUDE.md` asks it only of new code); raising pyright above `basic`; new features; translating
the new "Based on" string.

## 4. Do not touch

- Behaviour: no block changes what the app does. A pyright fix that would is a real defect (design
  4) and waits for the human.
- `docs/history/` content: the formatter does not touch Markdown, and `nothing_lost.py`'s logic
  only changes if a rule demands it.
- The human's files: the suite runs isolated (design 6); `make ui-check` already is.

## 5. Blocks

### B1 — Python 3.12 and the pyright configuration

- [ ] Design 1 (the five places), and `[tool.pyright]` from design 4 — not yet in the gate.
- [ ] `uv lock`.

**Verification:** `make ci`; `uv run pyright` runs with the config and reports its count (the
number goes in the log).

### B2 — Format the tree (its own commit)

- [ ] `git status` clean before starting; if not, stop and tell the human.
- [ ] `uv run ruff format .`; `format-check` added to `make ci`.

**Verification:** design 2's check; `make ci`; `make ui-check` green, screenshots looked at. Tell
the human to commit this block alone before B3.

### B3 — The rule set

- [ ] Design 3: `pyproject.toml` with the select and the commented ignores; the fixes.

**Verification:** `make ci`; `make ui-check` green, screenshots looked at.

### B4 — pyright at zero

- [ ] Fix by kind (design 4), file by file, `make ci` after each file.
- [ ] Real defects: listed in the log with their trigger; stop and ask before fixing any.
- [ ] `pyright` added to `make ci`; seen red.

**Verification:** `pyright` 0 errors; `make ci`; `make ui-check` green, screenshots looked at.

### B5 — The clock and the isolation

- [ ] `agent_tablet/clock.py`; `store.py:30` through it; the AST test (design 5), seen red.
- [ ] The conftest override and its test (design 6), seen red.
- [ ] `tests/clock_plugin.py`, its tests, `make test-midnight` (design 7); one run, its result in
      the log (a red there is a finding to report, not to fix in this block).
- [ ] `pytest-cov` and `make coverage` (design 8).

**Verification:** `make ci`; `make test-midnight` run once; `make coverage` prints its table.

### B6 — The exit

- [ ] `CLAUDE.md` "Local CI" and "Python" (old lines to `docs/history/root/CLAUDE.md`);
      `.claude/rules/python-tests.md`.
- [ ] `plans/00-STATUS.md`: this plan's row leaves §3, closing note to its history.

**Verification:** `make ci` (including `nothing_lost.py` at 0); `CLAUDE.md` under 300 lines.

## 6. Execution log

*(written by the executing session)*
