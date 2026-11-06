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

> Left §2 on 2026-11-06: decided (§1 1.19).
| 2.10 | Renaming and deleting a project. Recommended: any can be renamed; any but the last can be deleted, stopping its running sessions after a confirmation | Human | Plan 04 B1, B4 (written with the recommendation) |

> Left §2 on 2026-11-06: answered — the format is as assumed (plan 01, B2's log).
| 2.2 | The real format of the `custom-title` entry, checked against the human's own transcripts | Executor of B2 | B2 |

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

> Left §3 on 2026-11-06: B2 built.
| 4 | `01-agent-tablet-fork.md` B2 (Claude's name) | Written, ready to execute |

> Left §3 on 2026-11-06: plan 04 built.
| 6 | `04-projects-and-tabs.md` (projects, the session list, tabs, windows; replaces B3) | Written 2026-11-06, ready to execute after B2; its B0 needs the human's go-ahead |

> Left §3 on 2026-11-06: B0's interactive results confirmed `&& exit`.
| 6 | `04-projects-and-tabs.md` (projects, the session list, tabs, windows; replaces B3) | Built 2026-11-06 (B0–B6 and B7's documents); open: B0's interactive exit statuses, which confirm `&& exit`, and the human's check by hand. Not closed |

> Left §3 on 2026-11-06.
| 7 | `05-context-and-integrations.md` (plan 01 B4 — context ring, `--settings`, the integrations menu, usage capture) | B1–B2 built 2026-11-06 (statusline script, context model, ring — not yet shown anywhere); B3–B5 after plan 04 closes |

> Closed 2026-11-06 — plan 05, "Context % in the list, usage captured, and the integrations menu".
> Built: the app's statusline script (session readings, usage.jsonl), `--settings` on every Claude
> command, the context model and its ring in rows and tabs, the integrations menu with the global
> statusline (consented, removable, the user's own bar chained). Left open: the human's checks by
> hand (§2 2.11).

Plan 05's execution log, verbatim:

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

**B3 (2026-11-06)** — `--settings` goes last on every Claude command through a new
`Provider._session_flags()`; plan 04's tests that compare exact strings gained the flag at their
end, with its session's agreement. The command in the settings file was run through `sh -c` as
Claude Code will: it prints the bar and writes the session file. `sys.executable` is the Python
the app runs on, so a checkout run from its venv writes the venv's Python; any `python3` works.

**B4 (2026-11-06)** — One `ContextModel` per app, passed to each window; a window disconnects from
it when destroyed (the model outlives it), and reads are coalesced to one in flight per session
(tested: a burst of five costs two reads). The ring sits in `projectlist._SessionRow` after the
text and in the tab after its state dot; the tab shows the fullest of its panes. Demo data writes
an exact 65 % reading for "JWT auth"; `make ui-check` asserts it in the row and on the open tab,
and the walk's tab command shows `--settings …/claude-settings.json` — B3 end to end.

**B5 (2026-11-06)** — The chaining of the user's own statusline (design 6) is built here: the app
computes it (`integrations.chained_command()`) and writes it to
`$XDG_CONFIG_HOME/agent-tablet/chained-statusline.json`, which the standalone script reads — the
script cannot import the package. Deviation: `make ui-check` does not click the switch. Under
Broadway the page is drawn too narrow for the row to fit, a second click inside a dialog dropped
Playwright's connection, a click on the page tab could go unanswered, and Ctrl+, stopped working
after dialog clicks (`docs/ui-verification.md`); the walk reads the Integrations tab from the tree
and checks the isolated `settings.json` untouched, and installing and removing are tested on a
real file.

> Left §3 on 2026-11-06: plan 06's B1–B4 were built.
| 8 | `06-usage-report.md` (execution time and tokens per session, category and project; replaces plan 01 B6) | Written 2026-11-06; B1–B4 executable now (new files only), B5 after plan 04 closes |

> Left §3 on 2026-11-06.
| 8 | `06-usage-report.md` (execution time and tokens per session, category and project; replaces plan 01 B6) | B1–B4 built 2026-11-06 (`python -m agent_tablet.usage`); B5 (the Usage window) next |

> Closed 2026-11-06 — plan 06, "Usage: execution time and tokens per session, category and project".
> Built: the incremental cache of the transcripts with deduplicated tokens, execution and blocked
> time by who started each turn (15-minute idle rule), list prices, the report, `agent-tablet usage`
> and the Usage window. Left open: categories (§2 2.5, plan 01 B5) and the human's look at the
> window on real data (§2 2.12).

Plan 06's execution log, verbatim:

**B1 (2026-11-06)** — Beyond design 2: a sidechain replaying a main-thread response under another
request id (ccusage #913) is dropped, and a main-thread copy arriving later displaces such replays
(tested). The recorded fixture is a real response written three times (content scrubbed). Verified
on copies of three of the human's transcripts: 682 MB in 1.7 s, a second pass reads 0 bytes in
1 ms, and each session's output equals the per-file deduplication plus its subagents' tokens.

**B2 (2026-11-06)** — Spans (execution or blocked, with their start and end) are stored and clipped
at query time, so a local day is two local midnights. A turn half-read is carried across passes
in the file's row (`files.state`); spans carry their file, so a rewritten transcript drops its own
and nobody else's (found on review, tested). A wait on the human counts whole as blocked even past
15 minutes; the idle rule applies to gaps between agent activities. This session, from a copy:
2.64 h of execution (human 1.60, peer 1.03), 164 min blocked — consistent with §1's 159 min an hour
earlier.

**B3 (2026-11-06)** — Copied from the pricing page that day and confirmed by the human. Not
anticipated by the plan: cache reads on Fable/Mythos 5.1 (0.025× input) and Opus/Sonnet 5.5
(0.05×) are cheaper than the usual 0.1×; Claude Haiku 5.5 has two rows by request prompt size
(over 100k tokens); the 1M window is priced at the standard rate, so a `[1m]` id prices as its base.
US-only inference (1.1×) is not applied: transcripts do not say where a request ran.

**B4 (2026-11-06)** — Not anticipated: session names come from the transcripts themselves (the
latest `custom-title`, else `ai-title`, kept in the cache's `names` table) so the command line needs
no app state; projects are read from `projects.json` read-only (`Projects.load` would move a broken
file aside, a side effect a report must not have). The statusline's exact cost is summed per stretch
(a drop is a `/clear` starting over), tested. Run on the human's real data: the first pass read the
2 GB in 14.8 s, the next in 0.15 s; 7 days: 17.7 h of execution, 4.8 h blocked (4.2 h of it this
session, waiting on the human's answers), ~2,000M tokens, ~$762 at list price — every session under
"(no project)" because the human's own config has no projects yet (plan 04 is checked in a separate
worktree). B5 waits: `tools/ui/check.py` and `session.py` are held by the plan 04 session.

**B5 (2026-11-06)** — The Usage window reads in a thread with a SQLite connection of its own (the
module's objects stay in one thread) and keeps the last report on screen while the next is read.
Not anticipated: the demo's transcripts had no message ids, request ids or `turnOrigin`, so the
cache rightly ignored them; they now carry them, as real ones do. Durations under an hour show in
minutes (`usage.duration`, tested), since a short session read "0.0h". `make ui-check` has a run of
its own for the window (`usage`): it opens from the main menu, lists "Client work" and "JWT auth"
with an estimated cost. `agent-tablet usage` goes through the app's `main()` before any window.
Also fixed while here, flagged by the plan 04 session: the preferences step's font check could pass
without its click landing (the button already showed the monospace default); the demo now saves
"Sans 12" and the step requires it before the reset.

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
