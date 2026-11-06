# Plan 05 — Context % in the list, usage captured, and the integrations menu

> **Status:** written 2026-11-06. **B1 and B2 built 2026-11-06**; **B3–B5 wait for plan 04 to
> close**: they touch `providers.py`, `prefs.py`, `projectlist.py`, `spaces.py`,
> `scripts/make_demo_data.py` and `tools/ui/check.py`, which plan 04 holds until then.
>
> **Replaces:** plan 01 B4 ("Context % in the list"), and the capture half of plan 01 B6 (its
> report stays in plan 01).
>
> **Exit** (where each part goes when executed):
> - How the context reaches the list, why `--settings`, the estimate and its limits, the global
>   install and how it is undone → `docs/context.md`, one row in the `CLAUDE.md` docs table.
> - "The app passes its own Claude settings with `--settings`; it writes `~/.claude/settings.json`
>   only through the integrations menu" → `CLAUDE.md` "Product rules" (it refines the 2026-11-06
>   rule; the old lines go to `docs/history/root/CLAUDE.md`).
> - The ring and what the integrations menu offers → `README.md` features.
> - Hooks, not built → `docs/NOT_BUILT_YET.md`, with their trigger.
> - Plan 01 B4's section → a line pointing at this plan's topic in `plans/00-STATUS.md`.
> - The rest → `git log`.

---

## 1. Goal, and what exists

Each session's context use visible at a glance in the list and on its tab, exact when Claude Code
reports it and estimated (and marked so) when it does not; and from day one, a history of cost and
limits that plan 01 B6 will report on. Nothing written to the human's Claude settings unless they
accept it, piece by piece, and can undo it.

**What exists, verified 2026-11-06:**

- **The statusline payload** (Claude Code docs, `code.claude.com/docs/en/statusline.md`): on stdin
  the command receives `session_id`, `session_name` (the `-n` / `/rename` name, absent when none),
  `transcript_path`, `cwd`, `model.id`, `cost.total_cost_usd` (list price; back to 0 on `/clear`),
  `cost.total_duration_ms` (wall clock), `context_window.used_percentage` (may be `null` early),
  `context_window.context_window_size` (200000, or 1000000 for extended context),
  `context_window.total_input_tokens`, and `rate_limits.five_hour|seven_day.used_percentage` and
  `resets_at` (subscribers only, after the first response). It runs at session start, after each
  assistant message, after `/compact` and on a few other triggers, debounced 300 ms; stdout is the
  bar's text.
- **Settings layering** (`code.claude.com/docs/en/settings.md`): `claude --settings <file>` layers
  a settings file for that one session, above the user's and below managed settings, and writes
  nothing. Plugins can bundle hooks but **not** `statusLine`.
- **The app launches `claude` itself**: `ClaudeProvider.resume_command`, `new_command` and
  `continue_command` (`providers.py`) build the shell command a terminal tab types. Sessions the
  human starts elsewhere (a terminal, the orchestrator's `claude -n …`) are not launched by the app.
- **The human's `~/.claude/settings.json`** has no `statusLine` and no `hooks` today (read
  2026-11-06); it has other keys that Claude Code itself rewrites (`/config`, `/model`).
- **Transcripts** carry the model id (`claude-opus-5-5`, …) and each assistant message's `usage`
  (`input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`), but not the window
  size: an extended-context session looks the same.
- **Plan 04** gives each session row a place for "the context ring, plan 01 B4's" and builds the
  tab strip (`spaces.py`), but draws neither (plan 04 §3).
- `agent_tablet/clock.py` is the only clock; `agent_tablet/log.py` the only logging setup.

## 2. Design

**Decided by the human (2026-11-06):** the app's statusline reaches the sessions it launches
through `--settings`, and a global install for the others is an opt-in of the integrations menu;
without data, an estimate from the transcript, marked approximate. The display is **a small ring**
— green, yellow from 60 %, red from 80 % (plan 01 B4's thresholds) — **with the exact % in a
tooltip**, on the row and on the tab. **The usage history is captured now**; plan 01 B6 reports
it. From earlier: nothing is installed by default; each piece is consented to and removable on its
own (§1 1.12).

1. **The statusline script, `agent_tablet/statusline.py`**, standard library only and runnable on
   its own (`python3 <path>/statusline.py`: Claude Code runs it, not the app). Per run it:
   - writes `$XDG_CACHE_HOME/agent-tablet/sessions/<session_id>.json` atomically (temp + rename)
     with the fields the app reads (§2.4) and `updated_at` (`clock`-free: the script is not the
     app; it stamps `time.time()` and is listed as the second allowed reader in the AST guard,
     with this reason);
   - appends one line to `$XDG_CACHE_HOME/agent-tablet/usage.jsonl`: timestamp, `session_id`,
     `cwd`, `model.id`, `cost.total_cost_usd`, `cost.total_lines_added|removed`, the two
     rate-limit percentages — what the transcript does not hold. Execution time and tokens are
     **not** captured here: the transcripts already carry every message's timestamp and `usage`,
     for past sessions too (measured 2026-11-06), and plan 01 B6 reads them there. Raw values
     only: `/clear` resetting the cost is plan 01 B6's to reconcile;
   - prints the bar: the human's own statusline output when they have one (design 6), else
     `<session_name or short id> · <used>% · $<cost>`.
   A malformed or partial payload never raises: it writes what it has and prints what it can,
   because a failing statusline shows an error in every Claude session.
   *Tests* (`tests/test_statusline.py`, the script run as a subprocess on recorded payloads in
   `tests/data/statusline/`, `XDG_CACHE_HOME` at `tmp_path`):
   `test_a_full_payload_writes_the_session_file_and_one_usage_line`,
   `test_an_early_payload_with_null_percentage_still_writes_and_prints`,
   `test_a_payload_that_is_not_json_prints_a_fallback_and_exits_zero`,
   `test_two_runs_append_two_usage_lines_and_keep_one_session_file`.

2. **The settings the app passes**: at start the app writes
   `$XDG_CONFIG_HOME/agent-tablet/claude-settings.json` = `{"statusLine": {"type": "command",
   "command": "<python3> <absolute path of statusline.py>"}}`, and `ClaudeProvider`'s three
   commands append `--settings <that file>`. Written on every start, so a moved checkout heals
   itself. Cursor sessions are untouched. *Tests*:
   `test_every_claude_command_carries_the_app_settings` (resume, resume with fork, new, continue),
   `test_cursor_commands_do_not`, `test_the_settings_file_points_at_this_checkouts_script`.

3. **The context model, `agent_tablet/context.py`** (app side): a `Gio.FileMonitor` on the
   sessions cache directory keeps `{session_id: ContextReading}`, where `ContextReading` has
   `percentage`, `window`, `updated_at` and `source` ∈ {`statusline`, `estimate`}; a
   `"changed"` signal carries the session id. Reading happens off the main thread, results come
   back with `GLib.idle_add` (`CLAUDE.md`). When a session has no file, or its file is older than
   the transcript's last assistant message, it is **estimated**: the last assistant `usage`
   (input + cache creation + cache read) over the last window the statusline reported for that
   session, or 200 000 if it never reported — `source = estimate`. *Tests*:
   `test_a_statusline_file_becomes_an_exact_reading`,
   `test_no_file_gives_an_estimate_over_200k`,
   `test_an_estimate_uses_the_last_reported_window`,
   `test_a_file_older_than_the_transcript_falls_back_to_the_estimate`.

4. **One vocabulary across the boundary**: the field names the script writes and the ones
   `context.py` reads are one tuple in `agent_tablet/context_fields.py`, imported by both (the
   script adds its directory to `sys.path` to stay runnable alone). *Parity test*
   `test_the_script_writes_every_field_the_app_reads` — runs the script on the full payload and
   asserts the written keys equal the tuple (`CLAUDE.md`: an enum that crosses a boundary has a
   parity test).

5. **The ring, `agent_tablet/contextring.py`**: a small `Gtk.DrawingArea`; `level(percentage)` →
   `ok` < 60 ≤ `warn` < 80 ≤ `full`; the tooltip says "62 % of 200k" or "~62 % of 200k (estimate)";
   an estimate is drawn dimmed; no reading draws nothing (no empty ring). Placed in the session row
   (plan 04's `projectlist.py`) and in each tab of the strip (`spaces.py`). *Tests*:
   `test_the_level_changes_at_60_and_80` (59, 60, 79, 80), `test_the_tooltip_marks_an_estimate`.

6. **The integrations menu**, a page in Preferences, one row per piece the app can put into
   `~/.claude/settings.json`. Today one piece: **"Status line in every Claude session"** — for the
   sessions not started from the app. Accepting it:
   - reads the file, keeps a copy in `$XDG_STATE_HOME/agent-tablet/settings-backup/` with a
     timestamp, sets `statusLine` to the app's script, records in the app's state what it wrote and
     **the human's previous `statusLine`, if any**, and writes atomically;
   - when the human had their own statusline, the app's script **runs it** with the same stdin and
     prints its output instead of its own, so their bar does not change; the app only adds the
     side effects of design 1. The same chaining applies under `--settings`, which also outranks
     the user's `statusLine`.
   Removing it restores the previous `statusLine` exactly (or removes the key), only if the file
   still holds what the app wrote; if the human changed it since, the app leaves the file alone and
   says so. *Tests* (`tests/test_integrations.py`, a settings file in `tmp_path`):
   `test_installing_changes_only_status_line` (every other key deep-equal before and after),
   `test_removing_restores_the_previous_status_line_exactly`,
   `test_removing_leaves_a_file_the_human_changed_since`,
   `test_installing_twice_writes_once`, `test_a_settings_file_that_is_not_an_object_is_refused`.

**Rejected, and why:**

- **Writing `statusLine` into `~/.claude/settings.json` by default**: §1 1.12; `--settings` covers
  every session the app starts without writing anything.
- **A Claude Code plugin to carry the statusline**: plugins cannot set `statusLine` (docs).
- **Hooks for the context or the cost**: no hook event carries either; the statusline does. Hooks
  are deferred until something needs an event the statusline does not give (`docs/NOT_BUILT_YET.md`).
- **The estimate as the only source**: the transcript does not say the window size, so a
  1M-token session would read five times too full.
- **A number instead of a ring**: the human chose the ring with the number in its tooltip.
- **SQLite for `usage.jsonl`**: plan 01 B6 weighs it when it builds the report; a log of appended
  lines is what a statusline run can write safely in 300 ms.

## 3. Out of scope

The cost report and its reconciliation of `/clear` (plan 01 B6); categories (plan 01 B5); hooks of
any kind; Cursor sessions; a context alert or notification.

## 4. Do not touch

- `~/.claude/settings.json` outside design 6's accept and remove, and never in a test or a demo:
  tests use `tmp_path`, `make ui-check` its isolated `HOME`.
- Plan 04's files until it closes (the header lists them); after, only the lines this plan's blocks
  name.
- The transcripts: read, never written.

## 5. Blocks

### B1 — The statusline script and the usage capture (now)

- [ ] Tests of design 1 and the parity test of design 4 first, seen red.
- [ ] `agent_tablet/context_fields.py`, `agent_tablet/statusline.py`, the recorded payloads; the
      AST clock guard lists `statusline.py` as an allowed reader, with its reason.

**Verification:** `make ci`; by hand, `python3 agent_tablet/statusline.py < tests/data/statusline/full.json`
prints the bar and writes both files under a temporary `XDG_CACHE_HOME`.

### B2 — The context model and the ring (now)

- [ ] Tests of designs 3 and 5 first, seen red.
- [ ] `agent_tablet/context.py`, `agent_tablet/contextring.py` — not yet placed anywhere.

**Verification:** `make ci`; `make test-midnight` (`updated_at` comparisons).

### B3 — `--settings` on every Claude command (after plan 04)

- [ ] Design 2's tests, then the settings file and the flag in `providers.py`.

**Verification:** `make ci`; by hand, a new session from the app shows the app's bar in its
terminal and its file appears under `~/.cache/agent-tablet/sessions/`.

### B4 — The ring in the row and on the tab (after plan 04)

- [ ] `contextring` in `projectlist.py`'s row and `spaces.py`'s tabs; `context.py` created by the
      app and passed down. Where, as plan 04 built them (verified 2026-11-06): the ring goes in
      `projectlist._SessionRow`, next to the name; on the tab, `spaces.TabInfo` gains a reading the
      way it carries `color` (`spaces.py:31`, drawn at `:102`); per-session state comes from
      `MainWindow._session_states()` / `App.all_states()`, the pattern to mirror for readings.
- [ ] `scripts/make_demo_data.py` writes session files for two demo sessions (one at 65 %, one
      estimated); `tools/ui/check.py` gains a step: the two rings, with their tooltips.

**Verification:** `make ci`; `make ui-check`, the rings looked at in the screenshots (one yellow,
one dimmed); by hand with two real sessions, the ring matches each session's bar within one point
and updates within 5 s of a reply.

### B5 — The integrations menu (after plan 04)

- [ ] Design 6's tests first, seen red; `agent_tablet/integrations.py`; the Preferences page.
- [ ] `tools/ui/check.py`: the page shows the piece, not installed.

**Verification:** `make ci`; `make ui-check` (its isolated `HOME` has its own empty
`~/.claude/settings.json`, so accepting and removing is exercised there, never on the human's).

### B6 — The exit

- [ ] `docs/context.md`; `CLAUDE.md` (the rule and the docs row, old lines to the history);
      `README.md`; `docs/NOT_BUILT_YET.md` (hooks); plan 01 B4's section replaced by a pointer.
- [ ] `plans/00-STATUS.md`: this plan's row leaves §3, closing note to its history.

**Verification:** `make ci` with `nothing_lost.py` at 0.

## 6. Execution log

**B1 (2026-11-06)** — Deviation: the script reads the time through `agent_tablet/clock.py`, loaded
from its own directory like any sibling, instead of being listed as a second allowed reader in the
AST guard — that guard's file is plan 04's until it closes, and this way it needs no exception.
`context_fields.py` is not imported by the script at all (one module less to load in 300 ms); the
parity test holds the written keys to it. The bar's chaining to a human's own statusline (design 6)
is built with B5, where the app learns that command. Verified with `/usr/bin/python3`, as Claude
Code will run it: prints `lm-plan-200 · 62% · $1.23`, writes both files.

**B2 (2026-11-06)** — Found while typing it: a session file with `window: 0` would have divided by
zero in the estimate; it falls back to 200k (tested). Checked beyond the unit tests: a
`ContextModel` in a GLib loop, its transcript first giving an estimate (50 %), then the statusline
script run on the side, the monitor picking the file up and the reading turning exact (62 %), the
ring's tooltip following. `make test-midnight` green.
