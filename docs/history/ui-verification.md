# History of `docs/ui-verification.md`

## Traps, each already paid for

> Left on 2026-11-06: the human checked the native app, which opens popovers after typing.
- **Once a key has reached the app, popovers stop opening** — the main menu and "More Options"
  ignore clicks for the rest of the run, while ordinary buttons still work; reloading the page
  does not help. Event timestamps were checked and are monotonic; the cause is not found. Until it
  is, a walk opens menus before it types (`check.py`'s step order). Whether the native app has the
  same problem is an open question in `plans/00-STATUS.md`.

> Left on 2026-11-06: a click inside a dialog breaks input too, and a restarted app recovers.
- **Under Broadway, once a key has reached the app, popovers stop opening** — the main menu and
  "More Options" ignore clicks for the rest of the run, while ordinary buttons still work;
  reloading the page does not help. **The native app does not do this** (checked by the human on
  2026-11-06: text in the search, then the gear, and the menu opens), so it is Broadway's, not a
  bug to fix in the app. Event timestamps were checked and are monotonic; the cause is not found.
  A walk opens menus before it types (`check.py`'s step order).
