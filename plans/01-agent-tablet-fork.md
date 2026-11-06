# Plan 01 — agent-tablet: the fork of Agent Session Manager

> **Status:** B0 delivered 2026-11-05. B1 delivered 2026-11-05 (checked by hand by the human). B2 built 2026-11-06, pending the human's check by hand. **B3 is replaced by plan 04; B4–B6 are stubs** (goal, behaviour
> and verification, but no test named per decision): each goes through `/design-plan` before it is
> executed.
>
> **Exit** (where each part goes when executed):
> - What agent-tablet is, where it comes from and what changed from the original → `README.md`
>   (the GPL requires "a modified version, with a date").
> - Rules that constrain future code → `CLAUDE.md`.
> - How each addition works (names, projects, context, categories, metrics) → `docs/<subsystem>.md`.
> - The rest → `git log`. The plan is deleted when its last block is delivered.
>
> Written 2026-11-05 against `r4nd3l/agent-session-manager` at `07f72bd` (v1.1.1, 2026-10-30).
> Revised the same day: the fork is maintained on its own and is **not** kept mergeable with upstream
> (`plans/00-STATUS.md`), which removed the rules about not renaming the package and putting every
> addition in a separate module.

---

## 1. Why a fork and not a new application

Agent Deck was tried and rejected: to type into a session you have to enter and leave each one, and
it shows more information than is needed. Agent Session Manager **already has the model that is
wanted**: the list on the left, the session on the right where you type directly, tabs, split
panes, favorites, search and a quick switcher. It runs the real `claude` and never rewrites a
conversation.

What it lacks are additions on top of that base, not another base:

| Missing | Block |
|---|---|
| Showing the name the session has in Claude (`claude -n`, `/rename`) | B2 |
| Projects that remember their sessions, from any folder, and reopen the next day | Plan 04 (replaces B3) |
| Context % in the list | B4 |
| Categories (design, execution, review, delivery…) | B5 |
| Cost and time per category and per project | B6 |

Whatever is useful to anyone — B2 above all — may still be offered to the original author as a PR,
by hand; nothing here depends on it being accepted.

## 2. Rules of the fork (in `CLAUDE.md`)

- **The agents' data is read, never rewritten**, and the app's own state lives in
  `~/.config/agent-tablet/` and `~/.cache/agent-tablet/`. (The original already moves transcripts
  to the trash and deletes them on the user's confirmation; that stays. Anything new that writes
  under `~/.claude` is a human decision first; what goes into Claude's settings goes through the
  integrations menu, `CLAUDE.md`.)
- **A session's name is Claude's.** The app does not invent a second name to keep in sync (B2).
- **License:** GPL-3.0-or-later, like the original. `LICENSE`, Máté Molnár's copyright and the line
  in `debian/copyright` are kept; our own line is added for what is new.

## 3. Blocks

Every block closes with `make ci` green, plus its own verification.

### B0 — The fork, the environment and the baseline ✅ 2026-11-05

- Fork at `github.com/hernancontigiani/agent-tablet`; `upstream` remote added for reference.
- uv environment (`make venv`: `--system-site-packages`, dev tools in `[dependency-groups].dev` and
  `uv.lock`), `make ci` as the local gate.
- Removed: the hosted CI (`.github/`, `.gitlab-ci.yml`), the VitePress docs site (`docs/`) and the
  AUR / PPA packaging (`packaging/`). `debian/` and `scripts/build_deb.sh` stay for the future `.deb`.
- `CLAUDE.md`, `.claude/` (rules and skills) and `plans/` set up.

**Verified:** ruff clean and `84 passed` before touching any code, then the same under `make ci`
with `pytest -n auto`.

### B1 — Own identity (name, icon, app id, package)

**On "do we need another icon?":** the GPL does not require it — the original's icon is GPL too —
but it changes anyway, for two concrete reasons: nobody confuses this version with the original, and
**both can be installed at once** without clashing (the app id, the `.desktop` file and the config
directory are what would collide).

| What | Original | agent-tablet |
|---|---|---|
| Visible name | Agent Session Manager | Agent Tablet |
| Command | `agent-session-manager` | `agent-tablet` |
| Python package | `claude_session_manager` | `agent_tablet` |
| App id | `io.github.r4nd3l.AgentSessionManager` | `io.github.hernancontigiani.AgentTablet` |
| Icon | `data/icons/io.github.r4nd3l.AgentSessionManager.svg` | `data/icons/io.github.hernancontigiani.AgentTablet.svg` (already in the tree) |
| `.desktop` and `metainfo.xml` | `data/io.github.r4nd3l.…` | renamed, with the new id |
| Configuration | `~/.config/agent-session-manager/` | `~/.config/agent-tablet/` |
| pip / deb package | `agent-session-manager-gtk` | `agent-tablet` |
| Translation domain | `claude-session-manager` | `agent-tablet` |

The places to touch, from `grep -rl 'r4nd3l\|AgentSessionManager\|agent-session-manager\|claude-session-manager'`
on 2026-11-05: `app.py`, `i18n.py`, `state.py`, `window.py`, `data/install.sh`, `data/*.desktop`,
`data/*.metainfo.xml`, `debian/{changelog,control,copyright,rules,source/options}`,
`scripts/build_deb.sh`, `scripts/make_demo_data.py`, `po/*.po`, `po/generate.py`,
`pyproject.toml`, `README.md`. **Plus the package rename**: `git mv claude_session_manager agent_tablet`,
every `import`, the tests, `PKG` in the `Makefile`, `[project.scripts]` and
`[tool.setuptools.*]` in `pyproject.toml`. Run the grep again before starting; the list is a
snapshot.

- **Import the original's state once**: if `~/.config/agent-tablet/state.json` does not exist and
  the original's does, copy it, so names and favorites already set are not lost. The original
  already does this for its own rename (`_migrate_old_config`, `state.py:21`): imitate it, with its
  test.
- `README.md`: what agent-tablet is, that it is a fork of Agent Session Manager with a link and
  credit, the date of the fork, and the list of changes (the GPL asks to state that it is a
  modified version). The link to the original's docs site goes.
- `debian/copyright`: our copyright line is added for what is new; the original author's stays.
- The icon is **provisional** (decided 2026-11-05): a tablet with the list on the left and the
  active pane on the right. It replaces the original's in `data/icons/`; the final one only
  replaces that file later.
- **Installation from source** (decided 2026-11-05: the `.deb` only once there is a first stable
  version). `data/install.sh` already installs the launcher and icon for the user pointing at the
  repo folder: it gets the new app id and is the way to install in this block. `debian/` is updated
  too so it does not keep the old identity, but no package is built.

**Verification:** with the original still installed, `./data/install.sh` and `agent-tablet` opens
**next to** the original with its own icon and name; it appears separately in the application menu;
and it starts with the names and favorites set in the original.

### B2 — A session's name is Claude's

**The defect:** the title comes from `store.display_name()` (`store.py:147`): name set in the app →
first message of the conversation → first 8 characters of the id. The name from `claude -n` or
`/rename` is never read, and `_scan_transcript` (`sessions.py:115`) only reads the first
`_MAX_SCAN_LINES = 50` lines.

**The new order:**
1. **Claude's name** (the last `custom-title` entry in the conversation file).
2. The name set in the app, **only for sessions that have no name in Claude**.
3. The title Claude generates by itself (`ai-title`).
4. The first message.
5. The id.

Why Claude goes first: sessions find each other by that name, and the orchestrator sets it with
`claude -n`. If the app took precedence there would be two names for the same session, drifting
apart without warning. **Renaming from the app a session that already has a name in Claude** shows a
notice: "this name comes from Claude; change it with `/rename` inside the session". The app does not
write into `~/.claude`, so it cannot change it itself.

**Cost:** the name can be on any line of the file (it is appended when you `/rename`), and some
files are many MB. It is not re-read on every refresh: the size already read is kept per file and
only what was appended since is read.

**Before writing code:** confirm the real format of the entry against one of the human's files:
`grep -h '"custom-title"' ~/.claude/projects/*/*.jsonl | head -3`. The `ai-title` format is verified
(`{"type":"ai-title","aiTitle":"…","sessionId":"…"}`); the `custom-title` one was assumed by
analogy.

**Verification:**
- Tests with sample files: name on line 3, on line 5,000, two renames (the last wins), no name,
  only `ai-title`; and the incremental read: a name appended after the first read is picked up
  without re-reading the start (assert the offset).
- By hand: `claude -n prueba-b2` in a terminal, send it a message, and the session appears in the
  list as `prueba-b2` without touching the app. Then `/rename prueba-b2-bis`, and the list changes on
  the next refresh.
- The `asm-sync-names.py` script is no longer needed.

### B3 — Replaced by plan 04 (2026-11-06)

Projects are designed in `plans/04-projects-and-tabs.md`: a project is a list of sessions from any
folder, not a set of folders, in one window. This block's earlier text is in git.

### B4 — Context % in the list

Replaced by plan 05 and delivered 2026-11-06: `docs/context.md` says how it works.

### B5 — Categories (stub)

- **A fixed list**, the phases of the software development life cycle: `plan`, `design`, `build`,
  `test`, `deploy`, `maintain`. The same for every project so they can be added up; not editable and
  not chosen per project, so it does not grow into a custom taxonomy (decided 2026-11-06).
- **A session with no category is `build`.**
- **Whether anything assigns categories automatically is open** (`plans/00-STATUS.md` §2): a
  pattern on the name is likely to guess wrong. Assigning by hand from the row's menu is in either
  way.
- Shown as a tag on the row, and the list can be filtered and grouped by category.
- **Never in the session's name**: it would break messaging between sessions by name.

**Verification:** a new session shows `build`; changing it by hand to `test`
survives a restart; filtering by one category in a project with sessions from three repos shows
the sessions of the three. The rest is written once the open questions are answered.

### B6 — Cost and time per category

Replaced by plan 06 and delivered 2026-11-06: `docs/usage.md` says how it works. What remains
is grouping by category, which waits for B5.

## 4. Out of scope, with the reason

| Topic | Why not now |
|---|---|
| Plans board (kanban) | Needs plans to have a machine-readable status line first (`> Status: …`), which is a convention change in every repo, not in this app |
| Active time with OpenTelemetry | Needs a backend (collector, Prometheus); B6 gives 80 % of it without infrastructure |
| Messaging between sessions from the app | Already works inside Claude; the app only has to show names right (B2) |
| Support for other agents (Cursor) | The original has it and it stays, but nothing is added to it |

## 5. Order and why

**B0 → B1 → B2 → plan 04 → B4 → B5 → B6.** B2 first among the additions because without names the app
is no use for the human's workflow ("if it doesn't pick up the name, it's no use to me"). Plan 04
(which replaces B3) before B4 because it is the other everyday annoyance. B4 leaves the statusline script that B6 reuses. B5
and B6 can be swapped. The toolchain baseline was delivered before B2 (2026-11-06), so the additions are
written under the final rules; `plans/00-STATUS.md` holds the order.

## 6. Decided (2026-11-05)

- **Repository:** `github.com/hernancontigiani/agent-tablet`. App id
  `io.github.hernancontigiani.AgentTablet`.
- **Maintained on its own**, not mergeable with upstream; the package is renamed in B1.
- **Icon:** provisional, delivered with the plan; the final one replaces it later.
- **Installation:** from source (`data/install.sh`) until a first version; the `.deb` after.
  Publishing the `.deb` is distribution, and the GPL's conditions are already met by the public
  repo.

## Execution log

**B1 (2026-11-05)**
- Package renamed with `git mv`; every `claude_session_manager` reference (imports, tests, `po/`,
  `debian/rules`, `scripts/`, `Makefile`, the `.desktop` `Exec=`) follows. The upstream commit
  history of each file is kept by the move.
- The state import is a rewrite of `_migrate_old_config`, not a second function: it now looks in
  `agent-session-manager/` first and the pre-rebrand `claude-session-manager/` second, copies once,
  and never writes there. Four tests, each seen red against an injected defect.
- The machine has no `msgfmt`, so `po/generate.py` cannot compile. The `.mo` files were rebuilt from
  the `.po` files with `polib` in a throwaway `uv run --with polib`; each keeps its 230 entries. The
  new About credit ("Based on") is untranslated and falls back to English.
- The About dialog names Hernan Contigiani as developer, keeps Máté Molnár in the copyright and adds
  a "Based on" credit. `debian/copyright` keeps the original's line and adds ours;
  `debian/changelog` gets an `UNRELEASED` entry, since no package is built.
- The metainfo said "the agents' own session data is never modified", which the trash and delete
  actions contradict; it now says the data is read, never rewritten, like the README.
- Not changed, deliberately: the `CSM_*` development environment variables (`CSM_APP_ID`,
  `CSM_PROJECTS_DIR`, `CSM_CLAUDE_CONFIG`) — not identity a user sees; the version stays 1.1.1;
  `data/screenshot.png` and `data/banner.png` still show the old name (only `banner.svg` was edited).
- `uv.lock` regenerated: the project name changed.
- **Checked by hand by the human, 2026-11-05:** installed with `./data/install.sh` next to the
  packaged Agent Session Manager; own entry, icon, title and About; `~/.config/agent-tablet/state.json`
  imported with the original's 2 names.

**B2 (2026-11-06)**
- The `custom-title` format was checked against the human's transcripts (read only):
  `{"type":"custom-title","customTitle":"…","sessionId":"…"}`, as assumed. Every file that has one
  also has an `agent-name` entry with the same value; the code reads `custom-title` only.
- `sessions.read_titles` keeps, per transcript, the bytes already read and the last name and
  `ai-title` found (`TITLE_SCANS`), and reads only complete lines appended since; a file that
  shrank is read again from the start. `session_title` holds the order: Claude's name, the app's,
  `ai-title`, the first message, the id. `SessionStore.display_name` calls it.
- Renaming a session Claude already named shows "This name comes from Claude" and changes nothing.
  A name the app stored earlier for such a session stays in `state.json`, unused.
- Tests in `tests/test_sessions.py`: line 3 and line 5,000, the last rename wins, no name with an
  `ai-title`, the incremental read (offset asserted, and the start overwritten so a re-read would
  lose the name), a half-written last line, a file that shrank, the title order, discovery. Each
  key one seen red against an injected defect from a throwaway test.
- `scripts/make_demo_data.py` names one demo session inside Claude, and `make ui-check` has a step
  `claude-name` that finds it under that name.
- The exit "how names work → `docs/<subsystem>.md`" needed no file: the rule is in `CLAUDE.md` and
  the why in `session_title`'s docstring.
- **For the human, by hand:** `claude -n prueba-b2`, one message, and the list shows `prueba-b2`;
  then `/rename prueba-b2-bis`, and the list follows on its next refresh.
