# Usage: execution time and tokens

How long Claude worked and how many tokens it used, per session, summed per category and per
project, for today, 7 days or 30 days — in the Usage window (main menu) and with
`agent-tablet usage [--period today|7d|30d] [--json]`. Both are `usage.report()` over one cache.

## Where the numbers come from

The transcripts Claude Code keeps under `~/.claude/projects/`, read only, past sessions included.
`agent_tablet/usage.py` reads each one from where the last pass stopped into
`$XDG_CACHE_HOME/agent-tablet/usage.sqlite` — derived data, rebuilt when its schema version
changes. On the human's 2 GB (2026-11-06) the first pass takes ~15 s, the next ones a fraction of a
second; a file that shrank or was replaced is read again and its old spans dropped.

**Tokens.** Every assistant response, **deduplicated by (message id, request id) across all files**:
a response is written once per content block and copied into resumed and forked transcripts;
without this the totals are 2–3× too high. The non-sidechain copy wins, then the larger; a sidechain
replaying a main-thread response under another request id is dropped. A subagent's transcript
(`<session>/subagents/*.jsonl`) counts for its parent. `<synthetic>` models and API errors do not
count; responses with only cache tokens do.

**Execution time** (this app's own definition; ccusage and agent-deck have none):

- a **turn** opens at the `user` entry carrying `turnOrigin` — who started it: the human, another
  session (`peer`), a background task (`task_notification`), `system`, `sdk`;
- its **execution** is from the opening entry to Claude's last activity before the next turn —
  the sum of the gaps between consecutive agent activities (assistant responses and tool results),
  so a long tool counts whole — **except a gap over 2 hours**, which is idle (a session left
  hanging and resumed the next day); the longest real tool measured ran 2h 1m (the human,
  2026-11-06);
- **subagents add no time of their own**: a turn that waits for them already holds their time,
  and when they run in the background after Claude answered, their completion opens a
  `task_notification` turn that counts like any other. Their tokens do count, for the parent;
- **blocked** is apart: from a tool call to its result when the human decided it (a
  `permissionDecision` whose source starts with `user`) or when the tool asks the human
  (`AskUserQuestion`), however long it took;
- time is stored as spans and clipped when reported, so a day is two local midnights and a turn
  across midnight splits there (`TZ` matters; `make test-midnight` covers it).

**Cost** is an estimate at list price (`agent_tablet/prices.py`, copied from Anthropic's pricing page
with its date and URL, confirmed by the human). Each response is priced at the rate in force on its
date; 5-minute and 1-hour cache writes are priced apart. When the app's statusline reported a
session's cost (`usage.jsonl`, `docs/context.md`), that exact figure replaces the estimate — summed
per stretch, since `/clear` starts the statusline's total over. On a subscription it is not a bill;
the 5-hour and 7-day limits, when the statusline reported them, are shown beside it.

**Names and projects.** A session is shown with the name the app gives it in the window, or in the
terminal with Claude's (`custom-title`, else `ai-title`) or its short id. Its project comes from
`projects.json` (read only in the terminal); a session in none goes under "(no project)", and every
session is under "(no category)" until categories exist.

## Rejected, and why

- **Rereading the transcripts on every report**: 3.6 s for 2 GB, and growing.
- **JSON for the cache**: hundreds of thousands of rows to deduplicate and sum by period.
- **Hooks to time turns**: only the sessions the app starts, and only from the day they are installed.
- **Wall-clock time** (`total_duration_ms`): counts the nights a session sat open.
- **Grouping by UTC day**: the human is at UTC−3.
- **A live price lookup**: no network; the table carries its date.

## Limits

US-only inference (1.1×) is not applied: the transcript does not say where a request ran. A price
change means a new row in `prices.py` with the day it took effect.
