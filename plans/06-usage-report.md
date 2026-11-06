# Plan 06 — Usage: execution time and tokens per session, category and project

> **Status:** written 2026-11-06. **B1–B4 are executable now** (new files only); **B5 waits for plan
> 04 to close** (`window.py`, `app.py` are its files) and shows categories once plan 01 B5 exists.
>
> **Replaces:** plan 01 B6 ("Cost and time per category"), whose stub and the lessons recorded there
> on 2026-11-06 this plan takes as its input.
>
> **Exit** (where each part goes when executed):
> - What is measured and exactly how — the turn, the idle gap, blocked time, deduplication, the
>   price table and its date — and why the alternatives were rejected → `docs/usage.md`, one row in
>   the `CLAUDE.md` docs table.
> - "Usage numbers come only from `agent_tablet/usage.py`" → `CLAUDE.md` "Python" (one bullet).
> - The Usage window and `agent-tablet usage` → `README.md` features.
> - Plan 01 B6's section → a pointer to this plan's topic in `plans/00-STATUS.md`.
> - The rest → `git log`.

---

## 1. Goal, and what exists

How long Claude worked and how many tokens it used, per session, summed per category and per
project, for today, 7 days or 30 days — with the time it waited on the human apart, and a cost
estimate beside it.

**What exists, measured 2026-11-06 on the human's transcripts (read only):**

- **Volume:** `~/.claude/projects/` holds 181 transcripts, 2.0 GB, 466,544 lines; reading every
  assistant line takes 3.6 s. Opening a report cannot reread everything.
- **Subagents:** 96 transcripts under `<project>/<session-id>/subagents/*.jsonl`; their tokens
  belong to the parent session.
- **Who started a turn:** the entry that opens a turn carries `turnOrigin` — `human`, `peer`
  (another session, e.g. the orchestrator), `task_notification` (a background task), `system`,
  `sdk` — on `user` entries only (counts on 30 transcripts: human 3,596, peer 1,607,
  task_notification 473). `promptSource` (`typed`, `queued`, `system`, …) and `origin` agree.
- **Waiting on the human:** a `tool_result` entry carries `permissionDecision`; `source: "config"`
  is automatic (14,770 + …), `source: "user_temporary"` (and other `user_*`) means the tool waited
  for the human (70 in the sample). An `AskUserQuestion` waits the same way.
- **Duplicates:** the same assistant response appears in several lines and files; deduplicating by
  (`message.id`, `requestId`) brings output tokens down 2–3× (this session: 1.09M → 380k).
- **Execution time, measured:** a turn = from its `turnOrigin` entry to its last assistant or
  tool-result entry. Raw, one session showed a 62-hour turn (resumed the next day). Dropping gaps
  over a threshold between consecutive agent activities: totals change little between 15 and 60
  min (orchestrator session 88.7 h raw → 11.4 h with any of them); this session 4.4 h raw → 2.2 h at
  15 min, of which 159 min were waits for the human's answers.
- **What ccusage and agent-deck do** (plan 01 B6's notes, 2026-11-06): neither measures execution
  time; ccusage's dedup and pricing are the reference; both group by UTC day.
- **Already built:** `agent_tablet/clock.py`; plan 05's statusline writes `usage.jsonl` with exact
  cost and the 5-hour / 7-day limits. Projects and their sessions are plan 04's
  (`projects.json`); categories are plan 01 B5's, not built (`plans/00-STATUS.md` §2 2.5).

## 2. Design

**Decided by the human (2026-11-06):** execution time counts **every turn, broken down by who
started it** (you / another session / a background task); a gap **over 15 minutes** between two
agent activities inside a turn is not execution; cost is shown **as a list-price estimate** next to
tokens and time, with the subscription limits when the statusline reported them; the report is a
**Usage window** opened from the main menu — a period selector and a tree project → category →
session — **and `agent-tablet usage`** in the terminal, with the same numbers.

1. **One reader, `agent_tablet/usage.py`, and a cache it owns**:
   `$XDG_CACHE_HOME/agent-tablet/usage.sqlite` (standard library `sqlite3`). It is derived data,
   rebuilt from the transcripts at any time, so it is not app state (`CLAUDE.md`'s state rule is
   about `state.json`/`projects.json`). Per transcript it records the byte offset read and the
   file's identity (inode, size); next time it reads only what was appended, and rereads a file
   whose size shrank or whose inode changed. A schema version in the cache: a new version
   rebuilds. *Tests* (transcripts written in `tmp_path`):
   `test_a_second_pass_reads_only_what_was_appended` (asserts the offset, and the totals equal a
   from-scratch read), `test_a_rewritten_transcript_is_read_again`,
   `test_a_new_schema_version_rebuilds_the_cache`.

2. **Tokens: every assistant entry, deduplicated** by (`message.id`, `requestId`) across all files,
   keeping the non-sidechain copy, then the one with the larger total. Without a `requestId`, the
   key adds the session id. `<synthetic>` models and `isApiErrorMessage` entries are not counted;
   entries whose only tokens are cache tokens are. A `subagents/*.jsonl` file counts for its parent
   session (the directory name). *Tests*: `test_a_response_logged_three_times_counts_once`,
   `test_the_non_sidechain_copy_wins`, `test_a_subagent_transcript_adds_to_its_parent`,
   `test_synthetic_and_api_errors_are_not_counted`, and a recorded fixture of a real duplicated
   response (scrubbed) with its expected totals.

3. **Execution time** (the definition this app owns; neither reference tool has one):
   - a **turn** opens at a `user` entry with `turnOrigin` and holds the agent activities after it —
     assistant entries and tool results — until the next one;
   - its **execution** is the sum of the gaps between consecutive activities (the first gap from
     the opening entry), **minus any gap over 15 minutes** (idle), **minus blocked time**;
   - **blocked** = for a tool result whose `permissionDecision.source` starts with `user`, or whose
     tool is `AskUserQuestion`, the time from its `tool_use` to its result; reported apart;
   - each turn's numbers are filed under its origin (`human`, `peer`, `task_notification`; `system`
     and `sdk` under "other") and under the **local date** its activity falls on, a turn crossing
     midnight split at midnight (`clock.py`).
   *Tests*: `test_execution_is_the_sum_of_gaps_between_activities`,
   `test_a_gap_over_15_minutes_is_idle` (14:59 counts, 15:01 does not),
   `test_a_permission_wait_is_blocked_not_execution`, `test_an_ask_user_question_is_blocked`,
   `test_a_turn_is_filed_under_who_started_it`, `test_a_turn_across_midnight_is_split_at_local_midnight`
   (with `TZ` set and `make test-midnight`), `test_a_resumed_session_does_not_stretch_the_old_turn`.

4. **Cost, an estimate**: `agent_tablet/prices.py`, a table shipped with the app — per model, the
   price per million input, output, cache-write (5-minute and 1-hour) and cache-read tokens, **with
   the date it was copied and its source URL**, and the rate in force at each entry's time when a
   price changed. No network (`CLAUDE.md`). When `usage.jsonl` (plan 05) has the statusline's exact
   cost for a session, the report shows that instead and says so. An unknown model is counted in
   tokens and time and shown as "no price". *Tests*: `test_cost_prices_each_token_kind`,
   `test_one_hour_cache_writes_cost_twice_input`, `test_an_unknown_model_has_tokens_but_no_price`,
   `test_the_statusline_cost_replaces_the_estimate_for_its_session`.

5. **The report, `usage.report(period, now) -> list[Node]`**, a pure function over the cache: a
   tree project → category → session, each node with execution (total and by origin), blocked,
   tokens by kind, cost (and whether it is exact), plus the latest 5-hour and 7-day limit
   percentages. Project membership from plan 04's projects; sessions in no project under "(no
   project)"; category "(no category)" until plan 01 B5 exists. Periods: today, 7 days, 30 days, in
   local days. *Tests*: `test_a_node_is_the_sum_of_its_children` (a number in prose is asserted:
   project = Σ categories = Σ sessions), `test_the_7_day_period_ends_today_at_local_midnight`,
   `test_a_session_in_no_project_is_reported_under_no_project`.

6. **Two ways to see it, the same numbers**: `python -m agent_tablet.usage [--period 7d] [--json]`
   now, which becomes `agent-tablet usage` when the app's `main()` can take a subcommand (B5); and
   the **Usage window** (B5): the period selector, the tree as in the human's chosen mock-up,
   execution, blocked, tokens, cost marked "estimate", and the limits line. Read off the main
   thread; the window shows the last report at once and refreshes when the cache catches up.
   *Test*: `test_the_cli_and_the_report_agree` (the JSON output equals `report()` for the same
   fixture).

**Rejected, and why:**

- **Rereading the transcripts on every report**: 3.6 s for 2 GB today, and growing.
- **JSON for the cache**: hundreds of thousands of rows to deduplicate and sum by period; SQLite is
  in the standard library and the cache is disposable.
- **Hooks to time turns**: they would see only the sessions the app launches, from the day they are
  installed; the transcripts have every session, past ones included.
- **Wall-clock time** (`total_duration_ms`): counts the nights a session sat open.
- **Counting only the human's turns**: the human chose every turn, broken down by who started it.
- **Grouping by UTC day** (ccusage, agent-deck): the human is at UTC−3; a late evening would land on
  the next day.
- **A live price lookup**: the app makes no network connections; the table carries its date.

## 3. Out of scope

Budgets and alerts; projections and burn rate; charts; export to CSV; Cursor sessions (they keep
their own transcripts); assigning categories (plan 01 B5).

## 4. Do not touch

The transcripts (read, never written); `~/.claude` in tests (`tmp_path` only); plan 04's files until
it closes.

## 5. Blocks

### B1 — The cache, the incremental read and deduplicated tokens (now)

- [ ] Tests of designs 1 and 2 first, seen red; a scrubbed fixture of a duplicated response.
- [ ] `agent_tablet/usage.py` (ingest, cache, tokens).

**Verification:** `make ci`; by hand on a copy of three of the human's transcripts in the
scratchpad: the token totals equal ccusage's method (the dedup measured in §1), and a second run
reads 0 new bytes.

### B2 — Execution time (now)

- [ ] Tests of design 3 first, seen red; the turn and time model in `usage.py`.

**Verification:** `make ci`; `make test-midnight`; by hand, this session's numbers from the copy
match §1's measurement within a minute.

### B3 — Prices (now)

- [ ] `agent_tablet/prices.py`, copied from Anthropic's published pricing on the day of execution,
      with that date and URL; the human looks at the table before it is used.
- [ ] Tests of design 4 first, seen red.

**Verification:** `make ci`; the human has confirmed the table.

### B4 — The report and the command line (now)

- [ ] Tests of designs 5 and 6 (CLI), seen red; `report()`; `python -m agent_tablet.usage`.

**Verification:** `make ci`; `python -m agent_tablet.usage --period 7d` on the human's real data,
read only, its output shown to the human.

### B5 — The Usage window and `agent-tablet usage` (after plan 04)

- [ ] The main-menu item, the window (`agent_tablet/usagewindow.py`), `main()` taking `usage`.
- [ ] `tools/ui/check.py`: a step opening the window on the demo data; `make_demo_data.py` writes
      transcripts whose numbers the step asserts.

**Verification:** `make ci`; `make ui-check`, the window looked at; by hand with the human's data.

### B6 — The exit

- [ ] `docs/usage.md`; `CLAUDE.md` (bullet and row); `README.md`; plan 01 B6 → pointer.
- [ ] `plans/00-STATUS.md`: this plan's row leaves §3, closing note to its history.

**Verification:** `make ci` with `nothing_lost.py` at 0.

## 6. Execution log

*(written by the executing session)*
