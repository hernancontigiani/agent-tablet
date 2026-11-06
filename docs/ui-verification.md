# Seeing the UI

How a session looks at its own UI change: an isolated instance of the app under GTK's **Broadway**
backend (which draws the app into a web page), driven by **Playwright** on the installed Google
Chrome, headless. It never uses the human's Chrome, their running instance, or their files
(`CLAUDE.md`).

## The commands

| Command | What it does |
|---|---|
| `make ui-check` | Starts an isolated instance with the demo sessions, walks the main screens, saves `NN-<step>.png` and `app.log`, prints where. Exit 1 on the first failing step, with its screenshot |
| `make ui` | Starts it and prints a URL; stays up until Ctrl+C |
| `make ui-watch` | The same, and restarts the app on every change under `agent_tablet/`; a page already open on the URL shows the new window without reloading |
| `uv run python -m tools.ui.session --smoke` | Starts, reports the windows and widget count, one screenshot, stops |

Options: `THEME=light|system` (dark by default, as the human uses it), `DEMO=empty` (no sessions),
`OUT=<dir>` (default: a new directory under `$TMPDIR`). A block that changes the UI ends with
`make ui-check` **and a look at its screenshots**: a green walk proves the screens open, not that
they look right.

**Writing a step or a script:** `with UiSession(out) as ui:` then `ui.click(type=..., text=...)`,
`ui.type(...)`, `ui.key(...)`, `ui.settle()` (the widget tree once the UI stops changing),
`ui.screenshot(name)`. Widgets are found by what they are — GTK type, any of their texts
(label, text, tooltip, title, placeholder) or a CSS class — and a match must be unique; an
ambiguous one lists the candidates.

## How it is built

- `tools/ui/launcher.py` runs the app unchanged and, when a request file appears, writes every
  mapped widget with its texts, CSS classes, focus and box. **The only code that runs inside the
  app**; `agent_tablet/` knows nothing of it.
- `tools/ui/session.py` gives each instance its own Broadway display and port, `dbus-run-session`
  bus, app id (`…AgentTablet.Dev`), `HOME` and XDG directories, and demo transcripts; every child
  is in its own process group and is killed by group on exit.
- `tools/ui/locate.py` turns a widget into page coordinates; `tools/ui/check.py` is the walk.

## Traps, each already paid for

- **Desktop portals hang the start.** Over the private bus nobody answers libadwaita's portal
  call, and the app waits forever. `ADW_DISABLE_PORTAL=1` and `GDK_DEBUG=no-portals` are set for
  the isolated instance; do not remove them.
- **A box is relative to its own surface.** A popover is a surface of its own, placed apart from
  the window; bounds computed against the window miss its items. Each widget is dumped relative to
  its native (window or popover), and each native is matched to its Broadway surface by size and
  shadow offset.
- **The tree is read after layout, and when it stops changing.** A widget mapped in this frame has
  no size until layout runs, and the session list fills in after start. The dump runs at idle
  priority, and `settle()` waits for two equal dumps; screenshots go through it.
- **A click is held for a moment.** A press and release in the same instant toggles a menu button
  open and shut before it paints.
- **Once a key has reached the app, popovers stop opening** — the main menu and "More Options"
  ignore clicks for the rest of the run, while ordinary buttons still work; reloading the page
  does not help. Event timestamps were checked and are monotonic; the cause is not found. Until it
  is, a walk opens menus before it types (`check.py`'s step order). Whether the native app has the
  same problem is an open question in `plans/00-STATUS.md`.
- **Dialogs come out narrower than on the desktop**, so their text wraps (the About title on two
  lines, Preferences' labels letter by letter). Do not judge a dialog's width from Broadway.
- **A killed `gtk4-broadwayd` leaves its socket file**; a display counts as taken only if something
  listens on it, and a session removes its own socket on exit.

## Rejected, and why

- **AT-SPI to find widgets**: GTK exports it only on Wayland and X11; under Broadway the app never
  appears in the registry, even with `GTK_A11Y=atspi`.
- **Chrome's own `--headless --screenshot`**: it captures before Broadway draws — a blank page.
- **A nested Wayland compositor** (weston, cage, mutter): none is installed, and each needs its own
  input injection; Broadway brings drawing and input through one browser.
- **A dump hook inside `agent_tablet/`**: development code in the shipped package.
- **A signal to request the dump**: a `SIGUSR1` handler installed through GLib never fired; a
  300 ms poll of a request file does.
- **In `make ci`**: it needs Chrome and `gtk4-broadwayd` and takes seconds per run.
