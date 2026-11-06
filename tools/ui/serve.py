"""`make ui` / `make ui-watch`: an isolated instance under Broadway, at a URL, until Ctrl+C.

With --watch the app restarts on every change under agent_tablet/; gtk4-broadwayd stays up, so a
page already open on the URL shows the new process's window without reloading.
"""

from __future__ import annotations

import argparse
import signal
import sys
import tempfile
from pathlib import Path

from tools.ui.session import REPO, THEMES, UiSession


def _exit_on_sigterm(*_args) -> None:
    raise KeyboardInterrupt


def serve(out: Path, theme: str, watch: bool) -> int:
    signal.signal(signal.SIGTERM, _exit_on_sigterm)  # the same clean teardown as Ctrl+C
    with UiSession(out, theme=theme, browser=False) as ui:
        print(f"open {ui.url}  (logs in {out}; Ctrl+C to stop)", flush=True)
        try:
            if not watch:
                signal.pause()
            from watchfiles import watch as watch_changes

            for changes in watch_changes(REPO / "agent_tablet"):
                ui.restart_app()
                print(f"restarted ({len(changes)} change(s))", flush=True)
        except KeyboardInterrupt:
            pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve an isolated instance under Broadway.")
    parser.add_argument("--watch", action="store_true", help="restart the app on source changes")
    parser.add_argument("--theme", choices=THEMES, default="dark")
    parser.add_argument("--out", type=Path, default=None, help="default: a new directory under $TMPDIR")
    args = parser.parse_args()
    out = args.out or Path(tempfile.mkdtemp(prefix="agent-tablet-ui-"))
    out.mkdir(parents=True, exist_ok=True)
    return serve(out, args.theme, args.watch)


if __name__ == "__main__":
    sys.exit(main())
