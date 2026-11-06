"""`make ui-check`: the standing walk over the main screens of an isolated instance.

Each step leaves a screenshot `NN-<step>.png` in --out; the first failing step stops the walk and
the exit code is 1. See docs/ui-verification.md.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

from tools.ui import locate
from tools.ui.session import THEMES, UiSession

APP_TITLE = "Agent Tablet"
CLAUDE_NAMED = "todo-api-tests"  # scripts/make_demo_data.py names it inside Claude
DEMO_PROJECT = "Client work"  # scripts/make_demo_data.py: the current project, mixing two folders
GROUP = "api pair"  # its group


class StepFailed(AssertionError):
    pass


def _expect(condition: bool, detail: str) -> None:
    if not condition:
        raise StepFailed(detail)


def _texts(tree: list[dict], css: str) -> list[str]:
    return [widget.get("label", "") for _win, widget in locate.find_all(tree, css=css)]


def step_title(ui: UiSession, shot: Callable[[], None]) -> str:
    titles = [window["title"] for window in ui.tree()]
    _expect(APP_TITLE in titles, f"no window titled {APP_TITLE!r}; windows: {titles}")
    return f"window {APP_TITLE!r}"


def _widgets(tree: list[dict]) -> list[dict]:
    return [widget for window in tree for widget in window["widgets"]]


def step_project_list(ui: UiSession, shot: Callable[[], None]) -> str:
    tree = ui.settle()
    names = _texts(tree, "heading")
    for expected in (CLAUDE_NAMED, "JWT auth", "Homepage redesign"):
        _expect(expected in names, f"{expected!r} is not in the project's list: {names}")
    headings = _texts(tree, "caption-heading")
    _expect(GROUP in headings, f"no {GROUP!r} group heading: {headings}")
    folders = set(_texts(tree, "caption"))
    _expect({"todo-api", "portfolio-website"} <= folders, f"the mixed project shows folders {folders}")
    shot()
    return f"{len(names)} sessions, the {GROUP!r} group, folder names shown"


def step_project_dropdown(ui: UiSession, shot: Callable[[], None]) -> str:
    ui.restart_app()  # a fresh process: Broadway's popovers stop opening after a dialog was used
    ui.click(type="Label", text=DEMO_PROJECT)
    labels = {w.get("label") for w in _widgets(ui.settle())}
    for expected in ("Default", "Dotfiles"):
        _expect(
            expected in labels, f"the dropdown does not show {expected!r}: {sorted(filter(None, labels))}"
        )
    shot()
    ui.click(type="Label", text="Dotfiles")
    names = _texts(ui.settle(), "heading")
    _expect(any("neovim" in n for n in names), f"Dotfiles shows {names}")
    folders = _texts(ui.tree(), "caption")
    _expect("dotfiles" not in folders, f"a single-folder project still shows its folder: {folders}")
    ui.click(type="Label", text="Dotfiles")  # the dropdown's face now names it
    ui.click(type="Label", text=DEMO_PROJECT)
    ui.settle()
    return "the dropdown lists the projects; switching shows each one's sessions"


def step_open_tab(ui: UiSession, shot: Callable[[], None]) -> str:
    # The walk's PATH starts with a stand-in "claude", so the tab runs without logging in anywhere.
    # Under Broadway, popovers stop opening once a terminal is up, so "Open beside" is checked by hand.
    # A third restart in one run cannot reach the display, so reopening on start is checked by hand.
    ui.restart_app()  # a fresh process: the dialog before took the popovers with it
    ui.click(type="Button", text="Actions for JWT auth")
    ui.click(type="Label", text="Open")
    tabs = [w.get("label", "") for w in _widgets(ui.settle()) if "JWT auth" in (w.get("label") or "")]
    _expect(len(tabs) >= 2, f"no tab for 'JWT auth' next to its row: {tabs}")
    shot()
    return "a session opens in a tab of its project"


def step_add_session(ui: UiSession, shot: Callable[[], None]) -> str:
    ui.click(type="Button", text="Add session")
    tree = ui.settle()
    types = {w["type"] for w in _widgets(tree)}
    _expect(
        "AddSessionDialog" in types, f"the Add session button opened no AddSessionDialog: {sorted(types)}"
    )
    labels = {w.get("label") for w in _widgets(tree)}
    for expected in ("Existing", "New", "TODO-API", "DOTFILES"):
        _expect(expected in labels, f"the dialog does not show {expected!r}")
    # Under Broadway, clicks inside this dialog do not reach it after the earlier steps' dialogs and
    # popovers; adding, moving and the New page are checked by hand.
    shot()
    _close_dialog(ui, "AddSessionDialog")
    return "the dialog opens on Existing, with the history by folder and a New page"


def _menu_is_open(tree: list[dict]) -> bool:
    """A PopoverMenu is among the window's natives."""
    return any(native["type"] == "PopoverMenu" for window in tree for native in window["natives"].values())


def _open_from_main_menu(ui: UiSession, item: str) -> list[dict]:
    ui.click_until(_menu_is_open, type="MenuButton", text="Main menu")
    ui.click(type="Label", text=item)
    return ui.settle()


def _close_dialog(ui: UiSession, dialog_type: str) -> None:
    ui.key("Escape")
    remaining = [w for win in ui.settle() for w in win["widgets"] if w["type"] == dialog_type]
    _expect(not remaining, f"{dialog_type} still open after Escape")


def step_preferences(ui: UiSession, shot: Callable[[], None]) -> str:
    tree = _open_from_main_menu(ui, "Preferences")
    types = {widget["type"] for window in tree for widget in window["widgets"]}
    _expect("PreferencesDialog" in types, "the Preferences item opened no PreferencesDialog")
    ui.click(type="Button", text="Reset to default font")
    fonts = [
        widget.get("label", "")
        for window in ui.settle()
        for widget in window["widgets"]
        if "monospace" in widget.get("label", "").lower()
    ]
    _expect(bool(fonts), "after resetting the font, the font button does not show the terminal's monospace")
    shot()
    _close_dialog(ui, "PreferencesDialog")
    return f"preferences opens, resets the font to {fonts[0]!r}, closes"


def step_about(ui: UiSession, shot: Callable[[], None]) -> str:
    tree = _open_from_main_menu(ui, f"About {APP_TITLE}")
    texts = {widget.get("label") for window in tree for widget in window["widgets"]}
    types = {widget["type"] for window in tree for widget in window["widgets"]}
    _expect("AboutDialog" in types, "the About item opened no AboutDialog")
    for expected in (APP_TITLE, "Hernan Contigiani"):
        _expect(expected in texts, f"the About dialog does not show {expected!r}")
    shot()
    _close_dialog(ui, "AboutDialog")
    return "about shows the name and the developer"


def step_no_traceback(ui: UiSession, shot: Callable[[], None]) -> str:
    log = ui.app_log()
    _expect("Traceback (most recent call last)" not in log, f"the app logged a traceback:\n{log[-2000:]}")
    return "no traceback in the app's output"


# Under Broadway, once a key or a click inside a dialog has reached the app, popovers stop opening
# for the rest of the run; the native app does not do this. So the step that only opens and closes
# a dialog goes first, and the ones that act inside the app come after the last menu they need.
STEPS = (
    ("title", step_title),
    ("project-list", step_project_list),
    ("about", step_about),
    ("preferences", step_preferences),
    ("project-dropdown", step_project_dropdown),
    ("add-session", step_add_session),
    ("open-tab", step_open_tab),
    ("no-traceback", step_no_traceback),
)


def run(out: Path, theme: str, demo: bool) -> int:
    with UiSession(out, theme=theme, demo=demo) as ui:
        for number, (name, step) in enumerate(STEPS, start=1):
            shots: list[Path] = []

            def shot(name: str = name, number: int = number, shots: list[Path] = shots) -> None:
                shots.append(ui.screenshot(f"{number:02d}-{name}"))

            try:
                detail = step(ui, shot)
            except (StepFailed, LookupError, TimeoutError, PlaywrightError) as failure:
                ui.screenshot(f"{number:02d}-{name}-FAILED")
                print(f"FAIL {number} {name}: {failure}")
                print(f"screenshots and app.log in {out}")
                return 1
            if not shots:  # a step that opens a dialog captures it while it is open
                shot()
            print(f"ok   {number} {name}: {detail}")
    print(f"screenshots and app.log in {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk the main screens of an isolated instance.")
    parser.add_argument("--theme", choices=THEMES, default="dark")
    parser.add_argument("--demo", choices=("full", "empty"), default="full")
    parser.add_argument("--out", type=Path, default=None, help="default: a new directory under $TMPDIR")
    args = parser.parse_args()
    out = args.out or Path(tempfile.mkdtemp(prefix="agent-tablet-ui-check-"))
    out.mkdir(parents=True, exist_ok=True)
    return run(out, args.theme, demo=args.demo == "full")


if __name__ == "__main__":
    sys.exit(main())
