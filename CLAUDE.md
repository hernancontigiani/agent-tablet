# CLAUDE.md — agent-tablet

`agent-tablet` is a native GTK4 / libadwaita desktop app, written in Python, for working with
several Claude Code (and Cursor) sessions at once: a session list on the left, the real agent
running in an embedded VTE terminal on the right, with tabs, split panes, search and a
quick switcher. It runs the real `claude` CLI; it does not reimplement the agent.

It started as a fork of [Agent Session Manager](https://github.com/r4nd3l/agent-session-manager)
at `07f72bd` (v1.1.1, 2026-10-30) and **is maintained on its own from 2026-11-05**: upstream is
not merged back on a schedule, and nothing here is shaped to stay mergeable with it. A change from
upstream is brought in by hand, as any other change, when it is worth it.

**Design decisions that constrain code are recorded here, as rules.** If a decision is not written
in this file, in `docs/` or in `plans/00-STATUS.md`, it is not decided anywhere a session can
read: ask rather than re-derive it.

## Where each thing lives

The axis is **how long each thing lives**. That decides which file a paragraph goes to, and keeps
what matters from being lost when a plan is deleted.

| Layer | Dies when | Lives in |
|---|---|---|
| What the app is, how to install and use it, what changed from upstream | Never | `README.md` |
| Rules that constrain code not written yet | When the code makes them obvious | This file |
| How a subsystem is built and why that way | With the code it describes | `docs/<subsystem>.md`, one row in the table below |
| What is deliberately deferred, with its trigger | When the trigger fires | `docs/NOT_BUILT_YET.md` |
| What is decided, open, and in flight | Kept current, never a narrative | `plans/00-STATUS.md` |
| Text that stopped being true: a previous rule, a closing note | Never; it only grows | `docs/history/`, never loaded |
| How something will be built | **When it is executed** | `plans/NN-*.md` |
| How a plan is written, executed and closed | Never | `plans/README.md`, `plans/ROLE-*.md` |

`docs/` is internal: it is not a published site.

**Subsystem docs** (one row each, with *when* to open it):

| Doc | Open it when |
|---|---|
| `docs/ui-verification.md` | Looking at a UI change, or writing a step of `make ui-check` |
| `docs/projects.md` | Changing projects, tabs or windows, or how a session is started or stopped |
| `docs/context.md` | Touching the context ring, the statusline script, `--settings` or the integrations menu |
| `docs/usage.md` | Touching execution time, tokens, prices, the Usage window or `agent-tablet usage` |

## Product rules the code must hold

Each one is broken by an ordinary-looking line of code.

- **The agents' data is read, never rewritten.** No code edits a transcript, `~/.claude.json` or
  anything else an agent owns. The only writes under `~/.claude` are the ones the user starts and
  confirms (moving a transcript to the trash, deleting it). **Any new write there is a decision for
  the human, recorded in `plans/00-STATUS.md` before the code** that does it exists.
- **What the app adds to Claude's settings (`~/.claude/settings.json`) — a statusline, hooks —
  goes through one integrations menu** (decided 2026-11-06): nothing is installed by default or as
  a side effect, each piece is accepted on its own with the user's explicit consent, and each one
  can be removed on its own at any time, leaving the rest of the file as the user had it. **What
  the app needs in the sessions it starts goes with `--settings`**, never into that file.
- **The app's own state lives in its own directories** (`$XDG_CONFIG_HOME/agent-tablet/`,
  `$XDG_CACHE_HOME/agent-tablet/` once the identity changes), never next to an agent's files.
- **A session's name is the one Claude has** (`claude -n`, `/rename`). The app never keeps a second
  name for a session that Claude already named, because the two would drift without warning and
  sessions find each other by that name.
- **A session belongs to one project at most, runs if and only if it has a tab, and is in at most
  one tab across every window; a project is open in at most one window.** Each pair of these keeps a
  session from being open twice, and a session from working where nothing shows it.
- **The app's own state is JSON in its own config directory** (`state.json`, `projects.json`),
  written whole through a temporary file.
- **Nothing is encoded into a session's name**: categories, projects and status are the app's own
  data. A name carrying them breaks messaging between sessions by name.
- **Nothing leaves the machine.** No telemetry, no update check, no crash reporting. The app makes
  no network connections of its own; only the agents it runs do.
- **Every user-visible string goes through `_()`** (`i18n.py`), and an error shown to the user is
  our own sentence, never `str(e)`.
- **License: GPL-3.0-or-later**, as upstream. The original copyright stays; `README.md` says this is
  a modified version, from when, and what changed.

## Python

- **uv manages the environment, and the venv is created with `--system-site-packages`.** PyGObject,
  GTK, libadwaita and VTE come from the system packages (`python3-gi`, `gir1.2-gtk-4.0`,
  `gir1.2-adw-1`, `gir1.2-vte-3.91`) and are never installed from PyPI; a plain `uv venv` imports
  nothing of the app. `make venv` does it right. Dev tools are `uv add --dev`, pinned in `uv.lock`.
- **The app has no runtime dependencies from PyPI**, and a new one is justified in the plan that
  adds it: the `.deb` has to ship it.
- **Python 3.12** is the target (decided 2026-11-05).
- **Never block the GTK main loop.** Scanning transcripts, reading large files and waiting on a
  process happen off the main thread; results come back with `GLib.idle_add`. Widgets are touched
  only from the main thread.
- **Paths are resolved when called, not at import.** A module-level `Path.home() / ...` cannot be
  pointed elsewhere by setting the environment, so a test that forgets to patch it reads the
  user's real files. Existing modules do it at import; new code does not.
- **Time is read only through `agent_tablet/clock.py`**, or passed in as a parameter: "idle for 5
  minutes", timers and cost windows must be testable at 23:59 and across midnight. A test walks
  the AST and fails on `datetime.now()`, `time.time()` and their kin anywhere else.
- **Errors are handled at the boundary they come from, once.** No `except Exception: pass`; a
  broad `except` names what it expects and logs what it swallows.
- **Usage numbers come only from `agent_tablet/usage.py`** (execution time, tokens, cost): the window,
  the command line and anything later read them there, so one definition of a turn holds everywhere.
- **Logging is configured in one place, `agent_tablet/log.py`**; a module only does
  `logging.getLogger(__name__)` (a test walks the AST for any other configuration). Identifiers go
  in `extra={...}`, not in the message. `AGENT_TABLET_LOG=debug` raises the level.
- **Enums that are serialized are `(str, Enum)`**, not `StrEnum`: it changes what `str(member)`
  returns.
- **Type hints on every signature, and pyright (basic) stays at zero errors.** An ignore is
  line-scoped, names its rule and the gap it covers — today only the VTE stubs, which lack GTK4's
  `Gtk.Widget` API on `Vte.Terminal`. A `None` pyright points at is either ruled out by the code
  (narrow it, behaviour unchanged) or a real defect (say so; do not paper over it).
- **A rule about the shape of the code** (never call X, never rebind `_` where it translates) is
  enforced by a test that walks the AST (`tests/test_code_rules.py`), not by `grep`: comments and
  strings fool a grep.
- Writing a test: `.claude/rules/python-tests.md` loads on its own when a test file is touched.

## Local CI

**There is no hosted CI, and that is a decision: no `.github/workflows/`.** `make ci` is the gate,
and a change is not done until it passes: `ruff check` (the rule set in `pyproject.toml`, each
ignore with its reason), `ruff format --check`, `pyright`, `pytest -n auto`, and
`docs/history/nothing_lost.py` (no line left a decision document without reaching its history).
Report the result with its output when a change is reported done; a skipped step is said to be
skipped. Outside the gate: `make test-midnight` (the suite at 23:30, in UTC) for anything that
reads the time, `make ui-check` for anything the user sees, `make coverage` as a report.

`make fmt FILES="..."` formats only the paths given (see the shared-tree rules below).

## How work moves: design → plan → execute → review

Work larger than a single change goes through `plans/`. The method — the shape of a plan, a stub
versus a written plan, the exit header, how one closes — is `plans/README.md`. Each role is loaded
with a skill rather than pasted by hand, so it cannot drift from what is versioned:

| Skill | When |
|---|---|
| `/design-plan` | Writing a plan another session can execute without rethinking it, or turning a stub into one |
| `/execute-plan` | Building a written plan, block by block |
| `/orchestrate` | Deciding what goes next and what runs in parallel, writing an execution session's launch prompt, closing a delivered plan |
| `/audit-architecture` | Asking whether a subsystem can change or grow without touching everything |
| `/review-branch` | Reviewing a branch for regressions before it is merged |
| `/compact-safe` | Before a context compaction, and right after one |

- **Decisions belong to the human.** When a choice is theirs, ask with concrete options and **one
  recommendation**, with the case in view (a screenshot, the real volume), then record it with its
  date in the file that owns it. Where something goes in the UI is a decision, not a deduction. Do
  not re-litigate what is recorded; if a new fact reopens it, say which part is reopened and why.
- **Verify against the tree before asserting.** Not the old plan, not memory of the repo, not a
  subagent's report — a report is a claim until checked.
- **No abstraction without a consumer.** Defer it with its trigger in `docs/NOT_BUILT_YET.md`.
- **See a test fail before trusting it.** A new check is run once against an injected defect (a
  temporary test, a `monkeypatch`), never by editing shared code, so it is known to be able to go
  red.
- **A number written in prose is asserted by a test or not written.** Prose has no way to go red.
- **An enum that crosses a boundary has a parity test** — between what a statusline script writes
  and what the app reads, between a category list and the rules that assign it.
- **A session sees its own UI change through Playwright, never the Chrome MCP tool and never the
  human's running instance** (decided 2026-11-05): an unattended, isolated run is reproducible and
  costs a fraction; the human's Chrome is theirs. How: `docs/ui-verification.md`.
- **The human tests by hand, with their own data.** Their config, their sessions and their
  `~/.claude` are not touched to set up a test or a demo; ask first.

## Git and the shared tree

Several sessions may work on this tree at once, and the human coordinates git.

- **Sessions do not commit, branch, tag or push** unless the human asks in that session. When they
  do, stage **by path**, never `git add -A` or `.`: the tree holds other sessions' half-written work.
- **No command that moves someone else's tree**: no `stash`, `checkout`, `reset`, `clean`, even with
  a commit authorised. That authorisation covers recording your own work, not moving anyone else's.
- **The same rule is about scope, and it covers processes and formatters too.** Stop a process by
  PID, never by `pkill` pattern — the human's own instance of the app is running too. Run
  `ruff format` and `ruff check --fix` on your own paths, never on the tree.
- **A file you created as new that `git status` shows as modified was not new**: you are
  overwriting someone else's. Look before taking the obvious name.

---

## Comment conventions

- **The default is no comment.** A comment is earned only when deleting it would lose something the
  identifier, the value and the surrounding code cannot express — almost always a footgun that will
  bite whoever edits next. **Fixing something is not what earns it.**
- **Never cite a document by name or section in a code comment** (`see docs/x.md §3`). Documents
  get deleted or merged, and the citation dangles. If the reasoning is worth keeping, inline the
  *why*. **`CLAUDE.md` is the exception**: it is maintained alongside the code.
- **A comment carries the WHY, never a restatement of the line below it.**
- **Say it once, in the shortest place that can hold it.** A decision belongs to exactly one file;
  everywhere else names the fact and stops. If a comment needs a second paragraph, it is in the
  wrong file or explaining something the code should express instead.
- **Verify a factual claim before leaving it in a comment.** A wrong comment is worse than none.
- **Don't explain library mechanics.** Comment the **domain** reason. A genuinely surprising
  footgun is documented **once**, here, never per call site.
- **Don't hedge a permanent decision as if it were temporary.** No "for now" / "yet" unless a
  follow-up is actually planned and recorded.
- **Don't describe the other side of a boundary.** The statusline script says what it writes, not
  what the app does with it.

## What earns a document

**The code is the source of truth for anything the code can answer**: the state file's shape, the
settings, the signals between widgets. A document that restates those does not stay correct — it
stays *plausible*, which is worse, because the reader cannot tell it has drifted.

A markdown file earns its place only when it records something the code **cannot**:

- intent and why-not (why a design was rejected, why a number means what it means),
- what is deliberately fake or unbuilt, and must not ship as-is,
- work that is planned but has no code yet.

Consequences:

- **A plan for shipped work is deleted, not archived** — once the thing exists, the plan is a
  second, worse description of it, and git keeps it. So **every plan declares its exit in its
  header**: which permanent file each part moves to when it is executed. Without that, the first
  thing lost is the why-not.
- **A doc never cites a plan by path**, because plan paths die on delivery. It says the topic has a
  plan and that `plans/00-STATUS.md` names it.
- **Decisions are written as current state with a date, in every document.** The why-not is state
  and stays: what was rejected and why describes what the system is not, and cannot be rebuilt.
  **The sequence is not written** — what was decided first and later reversed, "corrected on…", a
  struck-out item: **it goes verbatim to the document's history in `docs/history/`, in the same
  change**, and `make ci` checks no line is lost. Two versions of one fact living in one document
  is a contradiction, not history.
- **This file holds only what constrains code that doesn't exist yet, and stays under 300 lines.**
  Before adding a paragraph, ask what breaks if it is deleted. "Someone would undo a deliberate
  decision" → keep it, **phrased as a rule, not as the story of how we got there**. "Someone
  wouldn't know why that line is written that way" → it is a code comment. A subsystem gets one row
  in the docs table above, with the situation that sends a reader to it, never a section here.
  Raising the budget is the human's call, asked only after looking for what to cut.
- **A doc never asserts something the session's own environment can contradict.** When a doc takes
  a side against a tool that exists, it says the tool exists and why it isn't the default.

## `CHANGELOG.md`

**There is none until agent-tablet's first tagged release**: no entries are added or proposed before
there is a tag to roll back to. From then on it is written **only with the human's approval**: at
the end of a piece of work, propose the exact bullet for `[Unreleased]` and ask whether it belongs
there at all; never add, reword or drop an entry on your own initiative, and never treat one
approval as standing permission. A bullet is something the user experiences differently after
upgrading — not tooling, tests, refactors or docs — in the shortest sentence that answers "what can
I do now that I couldn't before?".

## Language

**Everything in this repository is in English**: code, comments, docs, plans, skills, commit
messages and this file. The conversation with the human may be in Spanish; what is written to the
tree is not. User-visible strings are English in the code and translated through `po/`.
