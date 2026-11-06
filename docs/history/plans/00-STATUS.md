# History of `plans/00-STATUS.md`

## Header

> Left the header on 2026-11-05, when the file became a live index with a line budget.
> Written as **current state with a date**, never as a narrative: the sequence is `git log`. If this
> file passes a few hundred lines, something here belongs in another file.

## 1. Decided

> Left §1 on 2026-11-05: plan 03 was delivered and its decision lives in its doc.
| 1.11 | UI checks by a session go through Playwright on an isolated instance; never the Chrome MCP tool or the human's instance | 2026-11-05 | `CLAUDE.md` · plan 03 |

## 2. Open

> Left §2 on 2026-11-06: decided — nothing installed for now; an integrations menu later (§1 1.12).
| 2.1 | Whether the app may install its statusline script into `~/.claude/settings.json` from Preferences (plan 01, B4) — the first write under `~/.claude` the app would start itself | Human | B4 |
> Left §2 on 2026-11-06: answered — the native app opens the menu after typing; it is Broadway's.
| 2.3 | Under Broadway, popovers stop opening once a key has reached the app (`docs/ui-verification.md`). Does the native app do the same — type in the search, then click the gear? | Human (a 10-second check); then whoever investigates | Menu steps after typing in `make ui-check` |

## 3. Roadmap and plans in flight

> Left §3 on 2026-11-05.
| 2 | `01-agent-tablet-fork.md` B1 (identity and package rename) | Written, ready to execute |
> Left §3 on 2026-11-05.
| 2 | `01-agent-tablet-fork.md` B1 (identity and package rename) | Built 2026-11-05; pending the human's manual check |

> Left §3 on 2026-11-05.
| — | `03-ui-verification.md` (Broadway + Playwright, reload on change) | Stub, spike proved the path — needs `/design-plan`; wanted before B2's UI work |

> Closed 2026-11-05 — plan 03, "Seeing the UI: Broadway + Playwright, isolated, reloaded on change".
> Built `tools/ui/` (launcher, session, locate, check, serve), `make ui-check`, `make ui`,
> `make ui-watch`, and `docs/ui-verification.md`; no code in `agent_tablet/`. Found while executing
> and not in the plan: portals hang the start; boxes must be relative to each native (popovers are
> surfaces of their own); the tree is read after layout and once stable; a click is held 120 ms;
> stale Broadway socket files; dialogs render narrower than on the desktop. Left open: popovers
> stop opening once a key has reached the app (§2.3), so the walk types last.

> Left §3 on 2026-11-06.
| 3 | `02-toolchain-baseline.md` | Stub — needs `/design-plan` |

## 4. Next plan number

> Left §4 on 2026-11-05: the next number is derived from `plans/`, so this line no longer changes.
**03.** Take it by creating the file, and update this line in the same act.

## 5. Delivered

> Left §5 on 2026-11-05: closing notes now go to this file instead of accumulating in the index.
## 4. Next plan number

> Left §4 on 2026-11-05: the next number is derived from `plans/`, so this line no longer changes.
**03.** Take it by creating the file, and update this line in the same act.

## 5. Delivered
A delivered plan leaves one short line here — what was built, the date, and anything left undone —
and is then deleted. Nothing yet.
