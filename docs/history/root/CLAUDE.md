# History of `CLAUDE.md`

## Where each thing lives

> Left the subsystem docs table on 2026-11-05, when `docs/ui-verification.md` became its first row.
| — | None yet. The first plan that builds a subsystem adds its row |

## Python

> Left "Python" on 2026-11-06, when plan 02 built the clock module and brought pyright to zero.
- **Time is injected.** Code that reads "now" takes it as a parameter or from one clock module,
  never `datetime.now()` / `time.time()` inline: "idle for 5 minutes", timers and cost windows must
  be testable at 23:59 and across midnight.
- **Type hints on every signature.** A rule about the shape of the code (never call X, never import
  Y) is enforced by a test that walks the AST, not by `grep`: comments and strings fool a grep.

## Local CI

> Left "Local CI" on 2026-11-05, when the history check joined the gate.
and a change is not done until it passes: `ruff check` and `pytest -n auto`. Report the result with

> Left "Python" on 2026-11-06, when agent_tablet/log.py became the one place.
- **Logging is configured in one place**, and nothing else calls `basicConfig`. Identifiers go in
  `extra={...}`, not in the message.

> Left "Local CI" on 2026-11-06, when format, pyright and the midnight run joined.
and a change is not done until it passes: `ruff check`, `pytest -n auto`, and
Report the result with
its output when a change is reported done; a skipped step is said to be skipped.

## What earns a document

> Left "What earns a document" on 2026-11-05: the sequence now goes to `docs/history/`, not to `git log`.
- **Decisions are written as current state with a date.** The why-not is state and stays; the
  sequence (what was decided first and later reversed) is `git log`.

## How work moves: design → plan → execute → review

> Left on 2026-11-05: plan 03 was delivered, and the rule points at its doc.
  costs a fraction; the human's Chrome is theirs. How: plan 03 (`plans/00-STATUS.md`).
