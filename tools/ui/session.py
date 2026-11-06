"""An isolated instance of the app under GTK's Broadway backend, driven by Playwright.

`UiSession` never reads or writes the human's files and never reaches their running instance: the
app gets its own session bus, app id, HOME and XDG directories, and demo transcripts. See
docs/ui-verification.md for how to use it and why it is built this way.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from tools.ui import locate

REPO = Path(__file__).resolve().parents[2]
DEV_APP_ID = "io.github.hernancontigiani.AgentTablet.Dev"
FIRST_DISPLAY = 20
BROADWAY_BASE_PORT = 8080
# Every variable whose value is a path the app may read or write. All of them point inside the
# session's directory; a test asserts it.
PATH_VARS = (
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "CSM_PROJECTS_DIR",
    "CSM_CLAUDE_CONFIG",
    "AT_UI_TREE",
)
THEMES = ("dark", "light", "system")


def port_of(display: int) -> int:
    return BROADWAY_BASE_PORT + display


def socket_name(display: int) -> str:
    return f"broadway{display + 1}.socket"


def allocate(socket_taken: Callable[[int], bool], port_taken: Callable[[int], bool], limit: int = 100) -> int:
    """The first display whose Broadway socket and port are both free."""
    for display in range(FIRST_DISPLAY, FIRST_DISPLAY + limit):
        if not socket_taken(display) and not port_taken(port_of(display)):
            return display
    raise RuntimeError(f"no free Broadway display between {FIRST_DISPLAY} and {FIRST_DISPLAY + limit}")


def socket_path(display: int) -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return Path(runtime) / socket_name(display)


def socket_taken(display: int) -> bool:
    """Something listens on the display's socket. A killed gtk4-broadwayd leaves the file behind,
    so the file alone says nothing."""
    path = socket_path(display)
    if not path.exists():
        return False
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(str(path)) == 0


def _port_taken(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def build_env(base: Path, display: int, base_env: Mapping[str, str]) -> dict[str, str]:
    env = dict(base_env)
    env.update(
        {
            "GDK_BACKEND": "broadway",
            "BROADWAY_DISPLAY": f":{display}",
            # Without these the app hangs at start now and then, waiting on a desktop portal over
            # the private bus that never answers.
            "ADW_DISABLE_PORTAL": "1",
            "GDK_DEBUG": "no-portals",
            "HOME": str(base / "home"),
            "XDG_CONFIG_HOME": str(base / "config"),
            "XDG_CACHE_HOME": str(base / "cache"),
            "XDG_DATA_HOME": str(base / "data"),
            "XDG_STATE_HOME": str(base / "state"),
            "CSM_PROJECTS_DIR": str(base / "projects"),
            "CSM_CLAUDE_CONFIG": str(base / "claude.json"),
            "CSM_APP_ID": DEV_APP_ID,
            "AT_UI_TREE": str(base / "tree.json"),
            "PYTHONPATH": str(REPO),
        }
    )
    return env


def write_isolated_state(config_home: Path, theme: str = "dark") -> None:
    if theme not in THEMES:
        raise ValueError(f"theme must be one of {THEMES}, not {theme!r}")
    state_file = config_home / "agent-tablet" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    data.setdefault("settings", {})["color_scheme"] = theme
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


class ProcessGroup:
    """Children each in their own process group, so closing kills them and everything they
    started — and nothing else."""

    def __init__(self) -> None:
        self._procs: list[subprocess.Popen] = []

    def spawn(self, cmd: list[str], env: Mapping[str, str], log: Path) -> subprocess.Popen:
        with open(log, "ab") as out:
            proc = subprocess.Popen(
                cmd, env=dict(env), stdout=out, stderr=subprocess.STDOUT, start_new_session=True
            )
        self._procs.append(proc)
        return proc

    def stop(self, proc: subprocess.Popen, timeout: float = 3.0) -> None:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                break
            try:
                proc.wait(timeout=timeout)
                break
            except subprocess.TimeoutExpired:
                continue
        if proc in self._procs:
            self._procs.remove(proc)

    def close(self) -> None:
        for proc in reversed(list(self._procs)):
            self.stop(proc)


_SURFACES_JS = """() => [...document.body.children].filter(e => e.style.position === 'absolute').map(e => {
  const r = e.getBoundingClientRect();
  const inner = e.firstElementChild;
  const m = inner && (inner.style.transform || '').match(/translate\\((-?[\\d.]+)px, (-?[\\d.]+)px\\)/);
  return {x: r.x, y: r.y, width: r.width, height: r.height,
          offset: m ? [Math.round(+m[1]), Math.round(+m[2])] : [0, 0]};
})"""


class UiSession:
    """`with UiSession(out) as ui: ui.click(type="SearchEntry"); ui.type("jwt")`."""

    def __init__(self, out: Path, *, theme: str = "dark", demo: bool = True, browser: bool = True) -> None:
        self.out = Path(out)
        self.with_browser = browser
        self.theme = theme
        self.demo = demo
        self.base = self.out / "session"
        self._procs = ProcessGroup()
        self._app: subprocess.Popen | None = None
        self._browser = None
        self._playwright = None
        self.page = None
        self.display = allocate(socket_taken, _port_taken)
        self.url = f"http://127.0.0.1:{port_of(self.display)}/"
        self.env = build_env(self.base, self.display, os.environ)

    # -- lifecycle -----------------------------------------------------------

    def __enter__(self) -> UiSession:
        try:
            self._prepare_data()
            self._start_broadway()
            self.start_app()
            if self.with_browser:
                self._start_browser()
            self.wait_for_window()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._procs.close()
        socket_path(self.display).unlink(missing_ok=True)

    def _prepare_data(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        for key in PATH_VARS:
            if key.endswith("HOME"):
                Path(self.env[key]).mkdir(parents=True, exist_ok=True)
        if self.demo:
            subprocess.run(
                [sys.executable, str(REPO / "scripts" / "make_demo_data.py"), "--root", str(self.base)],
                check=True,
                capture_output=True,
            )
        else:
            (self.base / "projects").mkdir(exist_ok=True)
        write_isolated_state(self.base / "config", self.theme)

    def _start_broadway(self) -> None:
        socket_path(self.display).unlink(missing_ok=True)  # free per allocate(): nobody listens
        self._broadway = self._procs.spawn(
            [
                "gtk4-broadwayd",
                "--port",
                str(port_of(self.display)),
                "--address",
                "127.0.0.1",
                f":{self.display}",
            ],
            env=os.environ,
            log=self.out / "broadway.log",
        )
        _wait(lambda: _port_taken(port_of(self.display)), 10, "gtk4-broadwayd did not start")

    def start_app(self) -> None:
        launcher = [sys.executable, str(REPO / "tools" / "ui" / "launcher.py")]
        self._app = self._procs.spawn(
            ["dbus-run-session", "--", *launcher], env=self.env, log=self.out / "app.log"
        )

    def restart_app(self) -> None:
        if self._app is not None:
            self._procs.stop(self._app)
        self.start_app()
        self.wait_for_window()

    def _start_browser(self) -> None:
        from playwright.sync_api import Error, sync_playwright

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(channel="chrome", headless=True)
        except Error as err:
            raise RuntimeError(
                "Google Chrome is needed to look at the UI (Playwright drives the installed one, "
                "headless): install google-chrome-stable."
            ) from err
        self.page = self._browser.new_page(viewport={"width": 1400, "height": 900})
        self.page.goto(self.url)

    def wait_for_window(self, timeout: float = 20) -> None:
        def ready() -> bool:
            if self._app is not None and self._app.poll() is not None:
                raise RuntimeError(f"the app exited; see {self.out / 'app.log'}")
            surfaces_ready = self.page is None or bool(self._surfaces())
            return surfaces_ready and bool(self.tree(timeout=2))

        _wait(ready, timeout, f"no window within {timeout}s; see {self.out / 'app.log'}")
        self.settle()

    def settle(self, timeout: float = 10) -> list[dict]:
        """The tree once two dumps in a row agree: the app has finished loading and laying out."""
        previous = self.tree()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.3)
            current = self.tree()
            if current and current == previous:
                return current
            previous = current
        raise TimeoutError(f"the UI kept changing for {timeout}s")

    # -- looking -------------------------------------------------------------

    def tree(self, timeout: float = 5) -> list[dict]:
        tree_file = Path(self.env["AT_UI_TREE"])
        request = tree_file.with_name(tree_file.name + ".req")
        request.touch()
        deadline = time.monotonic() + timeout
        while request.exists():
            if time.monotonic() > deadline:
                request.unlink(missing_ok=True)
                return []
            time.sleep(0.05)
        return json.loads(tree_file.read_text(encoding="utf-8"))

    def _surfaces(self) -> list[dict]:
        return self.page.evaluate(_SURFACES_JS) if self.page is not None else []

    def find(self, **match) -> tuple[dict, dict]:
        return locate.find(self.tree(), **match)

    def screenshot(self, name: str) -> Path:
        self.settle()
        self.page.wait_for_timeout(300)  # Broadway paints after GTK lays out
        path = self.out / f"{name}.png"
        self.page.screenshot(path=str(path))
        return path

    def app_log(self) -> str:
        log = self.out / "app.log"
        return log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""

    # -- acting --------------------------------------------------------------

    def click(self, settle_ms: int = 400, **match) -> dict:
        window, widget = self.find(**match)
        x, y = locate.page_point(window, widget, self._surfaces())
        # Held for a moment: a press and release in the same instant toggles a GtkMenuButton
        # open and shut before it paints.
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.wait_for_timeout(120)
        self.page.mouse.up()
        self.page.wait_for_timeout(settle_ms)
        self.settle()
        return widget

    def click_until(self, appears: Callable[[list[dict]], bool], tries: int = 2, **match) -> list[dict]:
        """Click until `appears(tree)` holds. A click on a menu button while a text entry has the
        focus can be spent moving the focus; the second one opens it."""
        for attempt in range(1, tries + 1):
            self.click(**match)
            tree = self.settle()
            if appears(tree):
                if attempt > 1:
                    print(f"  (click on {match} took {attempt} tries)")
                return tree
        raise LookupError(f"clicking {match} {tries} times did not bring up what was expected")

    def type(self, text: str, settle_ms: int = 600) -> None:
        self.page.keyboard.type(text, delay=40)
        self.page.wait_for_timeout(settle_ms)

    def key(self, keys: str, settle_ms: int = 400) -> None:
        self.page.keyboard.press(keys)
        self.page.wait_for_timeout(settle_ms)


def _wait(condition: Callable[[], bool], timeout: float, message: str) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError(message)
        time.sleep(0.2)


def _smoke(out: Path, theme: str) -> int:
    with UiSession(out, theme=theme) as ui:
        tree = ui.tree()
        widgets = sum(len(window["widgets"]) for window in tree)
        print(f"windows: {[window['title'] for window in tree]}  widgets: {widgets}")
        print(f"screenshot: {ui.screenshot('smoke')}")
        print(f"url: {ui.url}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start an isolated instance under Broadway.")
    parser.add_argument("--smoke", action="store_true", help="start, report, screenshot, stop")
    parser.add_argument("--theme", choices=THEMES, default="dark")
    parser.add_argument("--out", type=Path, default=None, help="default: a new directory under $TMPDIR")
    args = parser.parse_args()
    out = args.out or Path(tempfile.mkdtemp(prefix="agent-tablet-ui-"))
    out.mkdir(parents=True, exist_ok=True)
    if args.smoke:
        return _smoke(out, args.theme)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
