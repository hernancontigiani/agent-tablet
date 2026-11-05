# Plan 03 — Seeing the UI: Broadway + Playwright, isolated, reloaded on change

> **Status:** stub, 2026-11-05 — needs `/design-plan`. The spike below proved the path.
>
> **Exit:** how a session looks at its own UI change → `docs/ui-verification.md` (one row in the
> `CLAUDE.md` docs table); the rule that it never uses the human's Chrome or the human's running
> instance → `CLAUDE.md` (already there); the rest → `git log`.

## Goal

A session can see and drive the app it just changed, unattended, without installing it, without
the human's Chrome, and without touching the human's data or their running instance. While it
works, the app restarts by itself when a source file changes, so no step is "rebuild and relaunch".

## What exists — the spike of 2026-11-05 (scripts in the session's scratchpad, not in the tree)

- **GTK4's Broadway backend** renders the app into a web page: `gtk4-broadwayd --port 8087
  --address 127.0.0.1 :7`, then the app with `GDK_BACKEND=broadway BROADWAY_DISPLAY=:7`.
  `gtk4-broadwayd` is in the system packages.
- **Isolation**: `dbus-run-session` (its own session bus and AT-SPI registry, so the
  `GApplication` does not hand off to the human's running instance), `CSM_APP_ID=…AgentTablet.Dev`,
  `HOME` and the XDG variables pointed at the scratchpad, and the demo transcripts from
  `scripts/make_demo_data.py` through `CSM_PROJECTS_DIR` / `CSM_CLAUDE_CONFIG`.
- **Playwright for Python** (`uv run --with playwright`) on the installed Google Chrome
  (`channel="chrome"`, headless): no browser download. Page load + 2.5 s wait, screenshot: the
  window renders whole, with the demo's 5 projects and 7 sessions. A mouse click expanded
  Favorites.
- **Did not work:** Chrome's own `--headless --screenshot` (blank page: it captures before Broadway
  draws); typing into the search box after a click (no text arrived — focus or key forwarding, not
  diagnosed).
- `scripts/make_demo_data.py` writes to a fixed `/tmp/csm-demo`; the spike used a patched copy.

## To design

- **Reload on change**: the Broadway server stays up and the app process restarts on a change
  under `agent_tablet/` (a file watcher such as `watchfiles` in the dev group). Check whether the open
  Playwright page shows the new process's window without a reload, and what state is lost on
  restart (open tabs, which is acceptable for a look).
- **Locating widgets without coordinates**: Broadway draws surfaces, not DOM, so Playwright has no
  selectors. The app's AT-SPI tree lives on the same private session bus (`Atspi` is importable);
  find a widget by role and name, read its extents, click there. Spike before designing on it.
- **Keyboard input**: why the typed text did not arrive.
- **The entry points**: `make ui` (start isolated, print the URL), `make ui-watch`, and a
  `verify` script that walks the main screens and fails on a missing one, saving screenshots to the
  session's scratchpad and the app's stderr next to them.
- **Port and display per session**: two sessions verifying at once must not share them — a shared
  runtime resource (`plans/README.md`).
- **The demo data**: parametrize the output directory of `scripts/make_demo_data.py`; add the cases
  the coming blocks need (a Claude-named session for B2, a long transcript).
- **Theme**: the isolated config starts on the system light theme; the human uses the dark one.
  Decide which the checks capture, or both.
- **Playwright as a dev dependency** (`uv add --dev playwright`) using the system Chrome, versus
  `playwright install chromium`.
- **Not in `make ci`** unless it proves fast and stable: it needs a browser and a display server.

## Out of scope

An end-to-end suite with assertions over journeys; visual diffing against baselines.
