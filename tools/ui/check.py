"""`make ui-check`: the standing walk over the main screens of an isolated instance.

Each step leaves a screenshot `NN-<step>.png` in --out; the first failing step stops the walk and
the exit code is 1. See docs/ui-verification.md.
"""

from __future__ import annotations

import argparse
import json
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


def _rings(tree: list[dict]) -> list[str]:
    return [w.get("tooltip_text", "") for w in _widgets(tree) if w["type"] == "ContextRing"]


def step_context_rings(ui: UiSession, shot: Callable[[], None]) -> str:
    rings = _rings(ui.settle())
    _expect("65% of 200k" in rings, f"no exact 65% ring for 'JWT auth': {rings}")
    estimates = [tip for tip in rings if tip.endswith("(estimate)")]
    _expect(bool(estimates), f"no estimated ring for the sessions without a statusline file: {rings}")
    shot()
    return f"{len(rings)} rings: one exact at 65%, {len(estimates)} estimated"


def step_tab_ring(ui: UiSession, shot: Callable[[], None]) -> str:
    rings = _rings(ui.settle())
    _expect(rings.count("65% of 200k") >= 2, f"the 'JWT auth' tab shows no ring beside its row's: {rings}")
    shot()
    return "the open tab shows its session's ring"


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
    integrations = _check_integrations(ui, tree)

    def font_labels(tree: list[dict]) -> list[str]:
        return [
            w.get("label", "") for w in _widgets(tree) if w.get("label", "").startswith(("Sans", "Monospace"))
        ]

    before = font_labels(tree)
    # The demo saves "Sans 12": seeing it first is what makes the reset's click count.
    _expect(any(label.startswith("Sans") for label in before), f"the saved font is not shown: {before}")
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
    return f"preferences opens with {integrations}, resets the font to {fonts[0]!r}, closes"


def _claude_settings(ui: UiSession) -> dict:
    """The isolated instance's ~/.claude/settings.json; never the human's."""
    path = Path(ui.env["HOME"]) / ".claude" / "settings.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _check_integrations(ui: UiSession, tree: list[dict]) -> str:
    # No click: under Broadway, a click inside this dialog breaks the clicks after it, and the page
    # is drawn too narrow for its switch's row to fit. The page's tab shows it is there; turning the
    # switch on and off is tested against a real settings file in tests/test_integrations.py.
    tabs = [w.get("label") for window in tree for w in window["widgets"] if w.get("label") == "Integrations"]
    _expect(bool(tabs), "Preferences has no Integrations page")
    _expect(
        "statusLine" not in _claude_settings(ui),
        "opening Preferences wrote a statusLine to settings.json",
    )
    return "an Integrations page, settings.json untouched"


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
    ("context-rings", step_context_rings),
    ("about", step_about),
    ("preferences", step_preferences),
    ("project-dropdown", step_project_dropdown),
    ("add-session", step_add_session),
    ("open-tab", step_open_tab),
    ("tab-ring", step_tab_ring),
    ("no-traceback", step_no_traceback),
)


def _open_from_row(ui: UiSession, session: str, item: str) -> None:
    ui.click(type="Button", text=f"Actions for {session}")
    ui.click(type="Label", text=item)


def _tab_count(tree: list[dict], session: str) -> int:
    """How many widgets name the session besides its row: its tab's strip button and title."""
    return sum(1 for w in _widgets(tree) if session in (w.get("label") or "")) - 1


def _row_states(tree: list[dict]) -> list[str]:
    return [
        css
        for w in _widgets(tree)
        if "status-dot" in w.get("css", [])
        for css in w["css"]
        if css in ("working", "blocked", "done", "idle", "stopped")
    ]


def step_new_session_page(ui: UiSession, shot: Callable[[], None]) -> str:
    ui.click(type="SplitButton", text="New session (Ctrl+Shift+T)")
    tree = ui.settle()
    labels = [w.get("label") or "" for w in _widgets(tree)]
    for expected in ("Another folder…", "todo-api", "dotfiles"):
        _expect(expected in labels, f"the New page does not offer {expected!r}")
    _expect(
        any(
            w.get("placeholder") == "Search folders…" or w.get("text") == "Search folders…"
            for w in _widgets(tree)
        )
        or "Search folders…" in labels,
        "the New page has no folder search",
    )
    shot()
    return "the New page lists the folders to start in, by name, with a search"


def _faces(ui: UiSession) -> list[str]:
    """The project each window shows: the heading on its dropdown, one per window, sorted."""
    names = (DEMO_PROJECT, "Default", "Dotfiles")
    return sorted(
        w["label"]
        for win in ui.tree()
        for w in win["widgets"]
        if w["type"] == "Label" and w.get("label") in names and "heading" in w.get("css", [])
    )


def step_two_windows(ui: UiSession, shot: Callable[[], None]) -> str:
    ui.call("app._open_new_window")
    windows = [win for win in ui.tree() if win["title"] == APP_TITLE]
    _expect(len(windows) == 2, f"expected two windows, found {len(windows)}")
    _expect(
        _faces(ui) == [DEMO_PROJECT, "Default"], f"the new window does not take a free project: {_faces(ui)}"
    )
    ui.call("_select_project", "demo-1", on="default")  # the first window's project, from the second
    _expect(
        _faces(ui) == [DEMO_PROJECT, "Default"], f"a project held by the other window moved: {_faces(ui)}"
    )
    shot()
    return "a new window takes a free project; one held by the other window stays there"


def step_exit_closes_tab(ui: UiSession, shot: Callable[[], None]) -> str:
    _open_from_row(ui, "JWT auth", "Open")
    _expect(_tab_count(ui.settle(), "JWT auth") >= 1, "the session did not open in a tab")
    ui.type("/exit")
    ui.key("Enter", settle_ms=2500)  # the stand-in exits, and its shell with it
    tree = ui.settle()
    _expect(_tab_count(tree, "JWT auth") == 0, "the tab is still open after /exit")
    _expect("idle" not in _row_states(tree), f"a row still shows a running session: {_row_states(tree)}")
    shot()
    return "/exit inside the agent closes its tab and leaves the row stopped"


def step_reopen(ui: UiSession, shot: Callable[[], None]) -> str:
    _open_from_row(ui, "JWT auth", "Open")
    ui.settle()
    ui.wait(1500)  # the layout is written half a second after the change
    ui.restart_app()  # "Reopen tabs on start" is on by default
    tree = ui.settle()
    _expect(_tab_count(tree, "JWT auth") >= 1, "after a restart the tab of 'JWT auth' is not back")
    shot()
    return "a tab open when the app quit is open again on start"


def step_remove_from_project(ui: UiSession, shot: Callable[[], None]) -> str:
    _open_from_row(ui, "Homepage redesign", "Remove from project")
    names = _texts(ui.settle(), "heading")
    _expect("Homepage redesign" not in names, f"the removed session is still listed: {names}")
    _expect("JWT auth" in names, f"the other sessions left with it: {names}")
    shot()
    return "a session that is not running leaves the project without a question"


def step_delete_project(ui: UiSession, shot: Callable[[], None]) -> str:
    ui.click(type="Label", text=DEMO_PROJECT)
    deletes = locate.find_all(ui.tree(), type="Button", text="Delete project")
    _expect(len(deletes) == 3, f"expected a delete button per project, found {len(deletes)}")
    ui.click(nth=0, type="Button", text="Delete project")  # Default's: the projects are listed in order
    ui.click(type="Button", text="Delete")  # the confirmation
    ui.wait(500)
    # After a dialog, Broadway opens no more popovers: read what the app saved instead.
    saved = json.loads((ui.base / "config" / "agent-tablet" / "projects.json").read_text(encoding="utf-8"))
    names = [p["name"] for p in saved["projects"]]
    _expect(names == [DEMO_PROJECT, "Dotfiles"], f"after deleting Default the projects are {names}")
    shot()
    return "a project is deleted after its confirmation; the others stay"


# Each run starts its own isolated instance: under Broadway a dialog, a typed key or an open terminal
# leaves the rest of a run unable to open menus, so the walks that need one of them run alone.
# Clicks inside the Add session dialog never reach it (its rows and its buttons alike), so adding and
# moving a session from it is checked by hand; the rule behind them is in tests/test_projects.py.
def step_usage(ui: UiSession, shot: Callable[[], None]) -> str:
    _open_from_main_menu(ui, "Usage")
    labels: list[str] = []
    for _attempt in range(30):  # the window reads the demo transcripts off the main thread
        tree = ui.settle()
        usage = [window for window in tree if window["title"] == "Usage"]
        labels = [w.get("label", "") for window in usage for w in window["widgets"]]
        if "Client work" in labels:
            break
        ui.wait(500)
    _expect("Client work" in labels, f"the Usage window shows no 'Client work' project: {labels[:20]}")
    _expect("JWT auth" in labels, "the Usage window does not list 'JWT auth' under its project")
    _expect(any(label.startswith("~$") for label in labels), "the Usage window shows no cost estimate")
    shot()
    return "the Usage window lists the demo's projects and sessions, with an estimated cost"


RUNS: tuple[tuple[str, tuple[tuple[str, Callable[[UiSession, Callable[[], None]], str]], ...]], ...] = (
    ("main", STEPS),
    ("usage", (("usage", step_usage), ("no-traceback", step_no_traceback))),
    ("new-session-page", (("new-session-page", step_new_session_page),)),
    ("two-windows", (("two-windows", step_two_windows),)),
    ("exit-closes-tab", (("exit-closes-tab", step_exit_closes_tab),)),
    ("reopen", (("reopen", step_reopen),)),
    ("remove-from-project", (("remove-from-project", step_remove_from_project),)),
    ("delete-project", (("delete-project", step_delete_project),)),
)


# -- the real agent ---------------------------------------------------------------------------
# Opt in with --real-claude: the user's own `claude`, logged in, in a folder of the walk's own
# (DUMMY_FOLDER), sending a couple of one-word prompts. Claude writes its transcripts there as it
# always does; the app's config stays in the session.

DUMMY_FOLDER = Path.home() / ".cache" / "agent-tablet-ui" / "dummy"
REAL_PROJECT = "Real check"


def _wait_for(ui: UiSession, what: Callable[[], bool], seconds: float, failure: str) -> None:
    for _ in range(int(seconds * 2)):
        if what():
            return
        ui.wait(500)
    raise StepFailed(failure)


def _members(ui: UiSession) -> list[str]:
    saved = json.loads((ui.base / "config" / "agent-tablet" / "projects.json").read_text(encoding="utf-8"))
    return next(p["members"] for p in saved["projects"] if p["name"] == REAL_PROJECT)


def _start_real(ui: UiSession, name: str) -> None:
    ui.call("_start_new_session", str(DUMMY_FOLDER), None, None, name)
    ui.wait(6000)
    if "trust" in ui.terminal_text().lower():  # the first start in the folder asks; "No, exit" is first
        ui.key("ArrowDown")
        ui.key("Enter", settle_ms=4000)


def _ask(ui: UiSession, prompt: str, expect: str, seconds: float = 120) -> None:
    before = ui.terminal_text().count(expect)
    ui.type(prompt)
    ui.key("Enter")
    _wait_for(
        ui, lambda: ui.terminal_text().count(expect) > before, seconds, f"no {expect!r} after {prompt!r}"
    )


def step_real_new_session_joins(ui: UiSession, shot: Callable[[], None]) -> str:
    _start_real(ui, "at-check-a")
    names = _texts(ui.settle(), "heading")
    _expect("at-check-a" not in names, "the new session is listed before its first message")
    _ask(ui, "Reply with exactly the word pong and nothing else.", "pong")
    _wait_for(
        ui, lambda: "at-check-a" in _texts(ui.tree(), "heading"), 30, "the session did not join its project"
    )
    shot()
    return "a new session joins the project after its first message, not before"


def step_real_open_beside_and_exit(ui: UiSession, shot: Callable[[], None]) -> str:
    _start_real(ui, "at-check-b")
    _ask(ui, "Reply with exactly the word ping and nothing else.", "ping")
    _wait_for(ui, lambda: len(_members(ui)) == 2, 30, "the second session did not join")
    first = _members(ui)[0]
    ui.call("_open_beside", first)
    titles = [w.get("label", "") for w in _widgets(ui.settle()) if "│" in (w.get("label") or "")]
    _expect(titles != [], "the tab of two sessions is not named after both")
    shot()
    ui.type("/exit")  # into the pane that moved beside, which has the focus
    ui.key("Enter")
    _wait_for(
        ui,
        lambda: not any("│" in (w.get("label") or "") for w in _widgets(ui.tree())),
        30,
        "the pane of the session that exited is still there",
    )
    return "a session opens beside another, and /exit closes only its pane"


def step_real_reopen_resumes(ui: UiSession, shot: Callable[[], None]) -> str:
    ui.wait(1500)  # the layout is written half a second after the last change
    ui.restart_app()
    ui.wait(8000)
    _ask(ui, "Repeat the word you replied with before, in uppercase, and nothing else.", "PING")
    shot()
    return "after a restart the open tab resumes its conversation"


def step_real_ctrl_d(ui: UiSession, shot: Callable[[], None]) -> str:
    ui.key("Control+d")
    ui.key("Control+d", settle_ms=3000)
    _wait_for(ui, lambda: "terminal" not in json.dumps(ui.tree()), 30, "Ctrl+D twice did not close the tab")
    shot()
    return "Ctrl+D twice closes the tab"


REAL_STEPS = (
    ("new-session-joins", step_real_new_session_joins),
    ("open-beside-and-exit", step_real_open_beside_and_exit),
    ("reopen-resumes", step_real_reopen_resumes),
    ("ctrl-d", step_real_ctrl_d),
)


def write_real_project(config_home: Path) -> None:
    config = config_home / "agent-tablet"
    config.mkdir(parents=True, exist_ok=True)
    project = {"id": "real", "name": REAL_PROJECT, "members": [], "groups": []}
    (config / "projects.json").write_text(
        json.dumps({"version": 1, "current": "real", "projects": [project], "windows": []}), encoding="utf-8"
    )


def run_real(out: Path, theme: str) -> int:
    DUMMY_FOLDER.mkdir(parents=True, exist_ok=True)
    print(f"-- real-claude, in {DUMMY_FOLDER}")
    ok = run_one(out / "real-claude", theme, demo=False, steps=REAL_STEPS, real_agent=True)
    print(f"screenshots and app.log in {out}")
    return 0 if ok else 1


def run_one(out: Path, theme: str, demo: bool, steps, real_agent: bool = False) -> bool:
    with UiSession(out, theme=theme, demo=demo, real_agent=real_agent) as ui:
        for number, (name, step) in enumerate(steps, start=1):
            shots: list[Path] = []

            def shot(name: str = name, number: int = number, shots: list[Path] = shots) -> None:
                shots.append(ui.screenshot(f"{number:02d}-{name}"))

            try:
                detail = step(ui, shot)
            except (StepFailed, LookupError, TimeoutError, PlaywrightError) as failure:
                ui.screenshot(f"{number:02d}-{name}-FAILED")
                print(f"FAIL {number} {name}: {failure}")
                return False
            if not shots:  # a step that opens a dialog captures it while it is open
                shot()
            print(f"ok   {number} {name}: {detail}")
    return True


def run(out: Path, theme: str, demo: bool, only: str | None = None) -> int:
    failed = []
    for name, steps in RUNS:
        if only and name != only:
            continue
        if not demo and name != "main":
            continue  # the scenarios act on the demo's projects
        print(f"-- {name}")
        if not run_one(out / name, theme, demo, steps):
            failed.append(name)
    print(f"screenshots and app.log in {out}")
    if failed:
        print(f"failed: {', '.join(failed)}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk the main screens of an isolated instance.")
    parser.add_argument("--theme", choices=THEMES, default="dark")
    parser.add_argument("--demo", choices=("full", "empty"), default="full")
    parser.add_argument("--out", type=Path, default=None, help="default: a new directory under $TMPDIR")
    parser.add_argument("--run", choices=[name for name, _steps in RUNS], default=None, help="one run only")
    parser.add_argument(
        "--real-claude",
        action="store_true",
        help="the walks that need your own logged-in claude (sends prompts)",
    )
    args = parser.parse_args()
    out = args.out or Path(tempfile.mkdtemp(prefix="agent-tablet-ui-check-"))
    out.mkdir(parents=True, exist_ok=True)
    if args.real_claude:
        return run_real(out, args.theme)
    return run(out, args.theme, demo=args.demo == "full", only=args.run)


if __name__ == "__main__":
    sys.exit(main())
