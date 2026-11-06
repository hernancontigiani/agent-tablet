# History of `docs/ui-verification.md`

## Traps, each already paid for

> Left on 2026-11-06: the human checked the native app, which opens popovers after typing.
- **Once a key has reached the app, popovers stop opening** — the main menu and "More Options"
  ignore clicks for the rest of the run, while ordinary buttons still work; reloading the page
  does not help. Event timestamps were checked and are monotonic; the cause is not found. Until it
  is, a walk opens menus before it types (`check.py`'s step order). Whether the native app has the
  same problem is an open question in `plans/00-STATUS.md`.
