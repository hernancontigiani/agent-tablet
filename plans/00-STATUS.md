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
> Last updated: 2026-11-05.

## 1. Decided

| # | Decision | Date | Where it lives |
|---|---|---|---|
| 1.1 | Everything in the repository is in English; the conversation may be Spanish | 2026-11-05 | `CLAUDE.md` |
| 1.2 | Fork of `r4nd3l/agent-session-manager` at `07f72bd`, maintained on its own: not kept mergeable with upstream | 2026-11-05 | `CLAUDE.md` |
| 1.3 | No hosted CI: `make ci` is the gate. `.github/`, `.gitlab-ci.yml`, the VitePress site and AUR/PPA packaging removed | 2026-11-05 | `CLAUDE.md` · `docs/NOT_BUILT_YET.md` |
| 1.4 | uv with `--system-site-packages`; dev tools in `[dependency-groups].dev` and `uv.lock`; no PyPI runtime dependencies | 2026-11-05 | `CLAUDE.md` |
| 1.5 | Python 3.12; one ruff standard and pyright basic over the whole tree | 2026-11-05 | `CLAUDE.md` · plan 02 |
| 1.6 | `docs/` is internal, not a published site | 2026-11-05 | `CLAUDE.md` |
| 1.7 | Identity: Agent Tablet, `agent-tablet`, package `agent_tablet`, app id `io.github.hernancontigiani.AgentTablet`, provisional icon | 2026-11-05 | plan 01, B1 |
| 1.8 | Installation from source until a first stable version; the `.deb` after | 2026-11-05 | `docs/NOT_BUILT_YET.md` |
| 1.9 | A session's name is Claude's; the app keeps no second name for a named session | 2026-11-05 | `CLAUDE.md` · plan 01, B2 |
| 1.10 | The agents' data is read, never rewritten; any new write under `~/.claude` is decided here first | 2026-11-05 | `CLAUDE.md` |
| 1.11 | UI checks by a session go through Playwright on an isolated instance; never the Chrome MCP tool or the human's instance | 2026-11-05 | `CLAUDE.md` · `docs/ui-verification.md` |

## 2. Open

| # | Question | Owner | Blocks |
|---|---|---|---|
| 2.1 | Whether the app may install its statusline script into `~/.claude/settings.json` from Preferences (plan 01, B4) — the first write under `~/.claude` the app would start itself | Human | B4 |
| 2.2 | The real format of the `custom-title` entry, checked against the human's own transcripts | Executor of B2 | B2 |
| 2.3 | Under Broadway, popovers stop opening once a key has reached the app (`docs/ui-verification.md`). Does the native app do the same — type in the search, then click the gear? | Human (a 10-second check); then whoever investigates | Menu steps after typing in `make ui-check` |

## 3. Roadmap and plans in flight

| Order | Plan | State |
|---|---|---|
| 1 | `01-agent-tablet-fork.md` B0 | Delivered 2026-11-05 |
| 2 | `01-agent-tablet-fork.md` B1 (identity and package rename) | Delivered 2026-11-05 |
| 3 | `02-toolchain-baseline.md` | Stub — needs `/design-plan` |
| 4 | `01-agent-tablet-fork.md` B2 (Claude's name) | Written, ready to execute after 02 |
| 5 | `01-agent-tablet-fork.md` B3–B6 | Stubs inside plan 01 — each needs `/design-plan` |

## 4. Next plan number

The highest `NN` in `plans/` plus one, taken by creating the empty file. A delivered plan's number
is never reused (`git log --all -- 'plans/NN-*'` shows the ones already taken).

## 5. Closing a plan

Its row leaves §3, and its closing note — what was built, the date, what was left undone — goes to
`docs/history/plans/00-STATUS.md`. What it left open enters §2 in one line; what it decided goes to
the document that owns it.
