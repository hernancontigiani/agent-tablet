# History of `plans/00-STATUS.md`

## Header

> Left the header on 2026-11-05, when the file became a live index with a line budget.
> Written as **current state with a date**, never as a narrative: the sequence is `git log`. If this
> file passes a few hundred lines, something here belongs in another file.

> Left the header on 2026-11-06.
> Last updated: 2026-11-05.

## 1. Decided

> Left §1 on 2026-11-05: plan 03 was delivered and its decision lives in its doc.
| 1.11 | UI checks by a session go through Playwright on an isolated instance; never the Chrome MCP tool or the human's instance | 2026-11-05 | `CLAUDE.md` · plan 03 |

> Left §1 on 2026-11-06: plan 02 was delivered; the rule set lives in pyproject.toml.
| 1.5 | Python 3.12; one ruff standard and pyright basic over the whole tree | 2026-11-05 | `CLAUDE.md` · plan 02 |

> Left §1 on 2026-11-06: closing a tab stops its session again; projects stored as JSON.
| 1.13 | Projects replace folders as what the app opens on: one window, a project dropdown, a session in one project at most, Default empty from the first start, user groups, tabs of up to two panes, closing a tab never stops a session, stop closes its tab, quitting asks and stops all, "Reopen tabs on start" on by default. Favorites removed. Replaces plan 01 B3 | 2026-11-06 | plan 04 |

> Left §1 on 2026-11-06: the category list was given.
| 1.14 | Categories are a fixed list, the phases of the software development life cycle: not editable, not per project. A session with no category gets the development one. Replaces B5's editable global list | 2026-11-06 | plan 01, B5 |

## 2. Open

> Left §2 on 2026-11-06: decided — nothing installed for now; an integrations menu later (§1 1.12).
| 2.1 | Whether the app may install its statusline script into `~/.claude/settings.json` from Preferences (plan 01, B4) — the first write under `~/.claude` the app would start itself | Human | B4 |
> Left §2 on 2026-11-06: answered — the native app opens the menu after typing; it is Broadway's.
| 2.3 | Under Broadway, popovers stop opening once a key has reached the app (`docs/ui-verification.md`). Does the native app do the same — type in the search, then click the gear? | Human (a 10-second check); then whoever investigates | Menu steps after typing in `make ui-check` |

> Left §2 on 2026-11-06: decided (§1 1.15).
| 2.6 | Favorites already saved: imported into Default once, or dropped | Human | Plan 04 blocks |
| 2.7 | Whether Cursor sessions can be project members with the same rules | Human | Plan 04 blocks |

> Left §2 on 2026-11-06: answered (§1 1.14).
| 2.4 | The exact category list, and the name of the default one ("develop" or another) | Human | B5 |

> Left §2 on 2026-11-06: decided (§1 1.18).
| 2.8 | Several windows, one project in each (two monitors): allowed or not, and with which limits | Human | Plan 04 blocks |

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

> Left §3 on 2026-11-06: B3 replaced by plan 04; B5 reopened.
| 5 | `01-agent-tablet-fork.md` B3–B6 | Stubs inside plan 01 — each needs `/design-plan` |

> Left §3 on 2026-11-06: every product decision of plan 04 taken.
| 6 | `04-projects-and-tabs.md` (projects, the session list, tabs; replaces B3) | Stub 2026-11-06, decisions taken — needs `/design-plan` for its blocks; after B2 |

> Left §3 on 2026-11-06.
| 3 | `02-toolchain-baseline.md` | Written 2026-11-06, ready to execute |
| 4 | `01-agent-tablet-fork.md` B2 (Claude's name) | Written, ready to execute after 02 |

> Closed 2026-11-06 — plan 02, "Toolchain baseline: Python 3.12, one ruff standard, pyright at zero".
> Python 3.12 declared everywhere; the tree formatted once (its own commit, 2d287df); the lm-app
> rule set with commented ignores; pyright basic from 132 errors to 0, in the gate; the time read
> only through agent_tablet/clock.py, with an AST guard; tests isolated from the real HOME;
> make test-midnight and make coverage. Three real defects found and fixed with the human's
> choice: Continue in chat always failed (a shadowed `_`, now guarded by an AST test); a
> non-local location crashed seven actions (now a message); resetting the font did nothing.
> UiSession.close() orphaned instances when the browser died (fixed). Left undone: nothing.

Plan 02's execution log, verbatim:

**B1 (2026-11-06)** — A sixth declaration of the floor, not in design 1: `scripts/build_deb.sh`
(`python3 (>= 3.10)` in its generated control file); updated. pyright with the config: 132 errors.

**B2 (2026-11-06)** — Committed alone as `2d287df`. Every reformatted file parses to the same AST as
before except `providers.py`, where ruff added a space at the start of a docstring that began with a
quote. `git status` was not clean (another session's `.md` files and this plan's B1); none was a
`.py`, and the commit was staged by path.

**B3 (2026-11-06)** — `po/generate.py` also needs `E501` per file: a translation pair stays on one
line. `terminal.py:_request_update` swallows every exception in its worker thread so the idle
callback still runs; it became `contextlib.suppress(Exception)` with the same behaviour — it should
log what it swallows once logging exists.

**B4 (2026-11-06)** — 120 of the 132 errors were noise, fixed without behaviour change: a typed
`SessionStore.model_items()` for every walk of the model; `Pango.EllipsizeMode` instead of bare
ints; row classes with typed attributes (`_SwitchRow.payload`, `_KeyedRow.key`) instead of
attributes hung on `Gtk.ListBoxRow`; narrowing where `None` cannot happen. Checked before
"fixing": an idle callback returning a tuple runs once (PyGObject repeats only on `True`), so the
popover-release lambda was noise. Line-scoped ignores only for the VTE stubs (`Terminal` as a
`Gtk.Widget`, `get_text_range_format`, the `spawn_async` slots).

**Three real defects** (the other 12 errors), waiting for the human:
- **A.** `window.py:_on_resume_chat_action` unpacks `variant_key, _, session_id`, shadowing `_`;
  the `_("Chat — {name}")` below calls a string. "Continue in chat" from a session's menu always
  raises `TypeError`.
- **B.** A location that is not a local path (a network place not mounted through FUSE, a phone)
  makes `Gio.File.get_path()` return `None`, and the action fails: new session, advanced new session
  (`window.py` and `dialogs.py`), continue, new chat, export, open transcript — seven sites.
- **C.** Preferences → reset font calls `Gtk.FontDialogButton.set_font_desc(None)`, which GTK rejects
  (`TypeError`, verified); the reset does nothing.

The human chose (2026-11-06): fix A; B shows an error and does nothing else; C clears the setting
and shows the font a terminal uses. Built: A by renaming the variable, with an AST test
(`tests/test_code_rules.py`) that no function calling `_()` rebinds `_` — it found exactly this
site; B through one `dialogs.require_local_path()` used by all seven sites, tested with a remote
`Gio.File`; C reads VTE's default from an unattached `Vte.Terminal`, shows it on open and on reset
without saving it, and `make ui-check` now presses the reset. Each seen red first.

Also found in B4, in this plan's own tooling: `UiSession.close()` stopped before killing the app
when the Playwright driver had died, orphaning instances that then loaded the machine; it now
always stops its children (tested). And Broadway's input trouble is wider than "after typing": a
click inside a dialog has the same effect; `ui.restart_app()` recovers, so `check.py` runs About
before Preferences and restarts before the search (`docs/ui-verification.md`).

**B5 (2026-11-06)** — `agent_tablet/clock.py`; `store.py` reads through it; the AST guard found no
other read. The conftest override sets `HOME`, the XDG variables and the `CSM_*` paths before any
import. `make test-midnight` ran once: 125 passed; a probe confirmed each xdist worker sees
02:30 UTC (23:30 at −03:00). `make coverage`: 24% of `agent_tablet/` (4,551 statements), most of it
GTK code no unit test reaches — a number to read, not a target. The Makefile computes the instant
with GNU make's `shell` function: a shell command substitution in a recipe line was stopped by the
session's safety check before it ran.

> Left §3 on 2026-11-06: plan 04 written.
| 6 | `04-projects-and-tabs.md` (projects, the session list, tabs; replaces B3) | Stub 2026-11-06, every product decision taken — needs `/design-plan` for its blocks; after B2 |

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
