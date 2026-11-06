# Status — what is decided, what is open, what is in flight

> **The index of the whole design, kept current by every session.** Read it **before** designing or
> building anything. It does not explain decisions: it says where each one is explained. A decision
> recorded here is not re-litigated without saying so explicitly.
>
> **A live index, 300 lines at most.** It answers only: what is decided and where it lives, what is
> open and who decides it, which plan is in flight or a stub and what blocks it, and the numbering.
> Written as **current state with a date**; what stops being current leaves for
> `docs/history/plans/00-STATUS.md` in the same change, verbatim.
>
> Last updated: 2026-11-06.

## 1. Decided

| # | Decision | Date | Where it lives |
|---|---|---|---|
| 1.1 | Everything in the repository is in English; the conversation may be Spanish | 2026-11-05 | `CLAUDE.md` |
| 1.2 | Fork of `r4nd3l/agent-session-manager` at `07f72bd`, maintained on its own: not kept mergeable with upstream | 2026-11-05 | `CLAUDE.md` |
| 1.3 | No hosted CI: `make ci` is the gate. `.github/`, `.gitlab-ci.yml`, the VitePress site and AUR/PPA packaging removed | 2026-11-05 | `CLAUDE.md` · `docs/NOT_BUILT_YET.md` |
| 1.4 | uv with `--system-site-packages`; dev tools in `[dependency-groups].dev` and `uv.lock`; no PyPI runtime dependencies | 2026-11-05 | `CLAUDE.md` |
| 1.5 | Python 3.12; one ruff standard and pyright basic over the whole tree | 2026-11-05 | `CLAUDE.md` · `pyproject.toml` |
| 1.6 | `docs/` is internal, not a published site | 2026-11-05 | `CLAUDE.md` |
| 1.7 | Identity: Agent Tablet, `agent-tablet`, package `agent_tablet`, app id `io.github.hernancontigiani.AgentTablet`, provisional icon | 2026-11-05 | plan 01, B1 |
| 1.8 | Installation from source until a first stable version; the `.deb` after | 2026-11-05 | `docs/NOT_BUILT_YET.md` |
| 1.9 | A session's name is Claude's; the app keeps no second name for a named session | 2026-11-05 | `CLAUDE.md` · plan 01, B2 |
| 1.10 | The agents' data is read, never rewritten; any new write under `~/.claude` is decided here first | 2026-11-05 | `CLAUDE.md` |
| 1.11 | UI checks by a session go through Playwright on an isolated instance; never the Chrome MCP tool or the human's instance | 2026-11-05 | `CLAUDE.md` · `docs/ui-verification.md` |
| 1.12 | Nothing is installed into `~/.claude/settings.json` for now; when it is (statusline, hooks for usage), through an integrations menu where each piece is consented to and removable on its own | 2026-11-06 | `CLAUDE.md` |
| 1.13 | Projects replace folders as what the app opens on: one window, a project dropdown, a session in one project at most, Default empty from the first start, user groups, tabs of up to two panes, a session runs if and only if it has a tab (closing it stops the session, as today), quitting asks and stops all, "Reopen tabs on start" on by default. Favorites removed. Projects stored as JSON in the app's config directory. Replaces plan 01 B3 | 2026-11-06 | plan 04 |
| 1.14 | Categories are a fixed list, the phases of the software development life cycle: `plan`, `design`, `build`, `test`, `deploy`, `maintain`. Not editable, not per project. A session with no category is `build`. Replaces B5's editable global list | 2026-11-06 | plan 01, B5 |
| 1.15 | Saved favorites are dropped, not migrated: the key leaves `state.json`. Cursor sessions are project members under the same rules; Stop force-closes them, as Cursor has no clean exit | 2026-11-06 | plan 04 |
| 1.16 | A new session joins its project only once Claude has created it (its transcript exists, after the first message); one closed before that leaves nothing behind | 2026-11-06 | plan 04 |
| 1.17 | Upstream's other tab kinds stay, inside projects: chat and replay tabs belong to the current project but are not members and do not reopen; hidden sessions stay, in the "Add session" browser; fork and "continue last" join the current project like a new session; the quick switcher searches the current project; `Ctrl+B g` lists running sessions of every project; a new session's name is required, and the header's + opens "Add session" on "New" | 2026-11-06 | plan 04 |
| 1.18 | Several windows are allowed, one project open in at most one window: choosing it elsewhere brings its window forward; a window shows one project at a time and keeps the tabs of the ones it showed; closing a window asks and stops its sessions, the last one quits; "Move here" moves the tab across windows; reopening restores each window with its project and tabs; the blocked count spans every window | 2026-11-06 | plan 04 |

## 2. Open

| # | Question | Owner | Blocks |
|---|---|---|---|
| 2.2 | The real format of the `custom-title` entry, checked against the human's own transcripts | Executor of B2 | B2 |
| 2.5 | Whether categories are assigned automatically (by name pattern, or otherwise) or only by hand | Human | B5 |
| 2.9 | Tabs that are not agents — open, read and edit a file (text, Markdown, code) in the project's window — and whether a project names its folders to scope them | Human, in a design session of its own | Nothing yet |
| 2.10 | Renaming and deleting a project. Recommended: any can be renamed; any but the last can be deleted, stopping its running sessions after a confirmation | Human | Plan 04 B1, B4 (written with the recommendation) |

## 3. Roadmap and plans in flight

| Order | Plan | State |
|---|---|---|
| 1 | `01-agent-tablet-fork.md` B0 | Delivered 2026-11-05 |
| 2 | `01-agent-tablet-fork.md` B1 (identity and package rename) | Delivered 2026-11-05 |
| 4 | `01-agent-tablet-fork.md` B2 (Claude's name) | Written, ready to execute |
| 5 | `01-agent-tablet-fork.md` B4–B6 | Stubs inside plan 01 — each needs `/design-plan`; B5 reopened 2026-11-06 (§1 1.14) |
| 6 | `04-projects-and-tabs.md` (projects, the session list, tabs, windows; replaces B3) | Written 2026-11-06, ready to execute after B2; its B0 needs the human's go-ahead |

## 4. Next plan number

The highest `NN` in `plans/` plus one, taken by creating the empty file. A delivered plan's number
is never reused (`git log --all -- 'plans/NN-*'` shows the ones already taken).

## 5. Closing a plan

Its row leaves §3, and its closing note — what was built, the date, what was left undone — goes to
`docs/history/plans/00-STATUS.md`. What it left open enters §2 in one line; what it decided goes to
the document that owns it.
