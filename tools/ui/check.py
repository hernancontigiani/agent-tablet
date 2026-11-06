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
DEMO_PROJECTS = 5  # scripts/make_demo_data.py writes five projects
FAVORITES = "FAVORITES"


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


def step_history(ui: UiSession, shot: Callable[[], None]) -> str:
    groups = _texts(ui.tree(), "caption-heading")
    projects = [name for name in groups if name != FAVORITES]
    _expect(FAVORITES in groups, f"no {FAVORITES} group; groups: {groups}")
    _expect(
        len(projects) >= DEMO_PROJECTS,
        f"{len(projects)} project groups, expected at least {DEMO_PROJECTS}: {projects}",
    )
    return f"{len(projects)} projects + favorites"


def step_search(ui: UiSession, shot: Callable[[], None]) -> str:
    ui.click(type="SearchEntry")
    ui.type("jwt")
    sessions = _texts(ui.settle(), "heading")
    _expect(sessions == ["JWT auth"], f"after searching 'jwt' the list shows {sessions}")
    shot()
    ui.key("Control+a")
    ui.key("Backspace")
    return "'jwt' leaves only 'JWT auth'"


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
    shot()
    _close_dialog(ui, "PreferencesDialog")
    return "preferences dialog opens and closes"


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


# Typing goes after the menus: once a key has reached the app under Broadway, popovers stop
# opening for the rest of the run. The native app does not do this; it is Broadway's.
STEPS = (
    ("title", step_title),
    ("history", step_history),
    ("preferences", step_preferences),
    ("about", step_about),
    ("search", step_search),
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
