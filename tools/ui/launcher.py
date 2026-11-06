"""Run the app unchanged, plus a widget-tree dump and a method call a UiSession can request.

The only code of these tools that runs inside the app's process. It answers a request file instead
of a signal: a SIGUSR1 handler installed through GLib never fired under Broadway, a 300 ms poll did.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

TREE = os.environ["AT_UI_TREE"]
REQUEST = TREE + ".req"
# A call on the main window, for what a click cannot reach under Broadway (inside a dialog): the
# method the click would have run, by name, so what follows it runs as in the app.
CALL = TREE + ".call"
CALL_OUT = TREE + ".call.out"
_TERMINAL_TAIL = 4000
_TEXT_GETTERS = ("get_label", "get_text", "get_tooltip_text", "get_title", "get_placeholder_text")


def _describe(widget: Gtk.Widget, natives: dict) -> dict:
    entry: dict = {"type": type(widget).__name__, "css": list(widget.get_css_classes())}
    for getter in _TEXT_GETTERS:
        method = getattr(widget, getter, None)
        if method is None:
            continue
        try:
            value = method()
        except TypeError:  # a getter with this name that takes arguments
            continue
        if isinstance(value, str) and value:
            entry[getter.removeprefix("get_")] = value
    # Bounds relative to the widget's own native: a popover is a surface of its own, placed by the
    # compositor, and bounds computed against the window miss it by the popover's offset.
    native = widget.get_native()
    # Every GtkNative is a widget (a window or a popover); the stubs type it as the bare interface.
    assert isinstance(native, Gtk.Widget)
    # Keyed by order of discovery: a PyGObject wrapper's id() changes from one dump to the next, and
    # two equal trees must compare equal.
    key = next((k for k, seen in natives.items() if seen["object"] is native), f"n{len(natives)}")
    if key not in natives:
        x, y = native.get_surface_transform()
        natives[key] = {
            "object": native,
            "type": type(native).__name__,
            "size": [native.get_width(), native.get_height()],
            "surface_offset": [round(x), round(y)],
        }
    entry["native"] = key
    ok, bounds = widget.compute_bounds(native)
    if ok:
        entry["box"] = [
            round(bounds.get_x()),
            round(bounds.get_y()),
            round(bounds.get_width()),
            round(bounds.get_height()),
        ]
    entry["focus"] = widget.has_focus()
    text_format = getattr(widget, "get_text_format", None)  # a VTE terminal: what it shows
    if text_format is not None:
        from gi.repository import Vte

        text = text_format(Vte.Format.TEXT) or ""
        entry["terminal"] = text[-_TERMINAL_TAIL:]
    return entry


def _walk(widget: Gtk.Widget, natives: dict, out: list[dict]) -> None:
    if not widget.get_mapped():
        return
    out.append(_describe(widget, natives))
    child = widget.get_first_child()
    while child is not None:
        _walk(child, natives, out)
        child = child.get_next_sibling()


def dump() -> list[dict]:
    windows = []
    for top in Gtk.Window.list_toplevels():
        if not top.get_mapped():
            continue
        widgets: list[dict] = []
        natives: dict = {}
        _walk(top, natives, widgets)
        for native in natives.values():
            del native["object"]
        title = top.get_title() if isinstance(top, Gtk.Window) else None
        windows.append({"title": title or "", "natives": natives, "widgets": widgets})
    return windows


_pending = False
_calling = False


def _answer() -> bool:
    global _pending
    try:
        tmp = TREE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(dump(), handle, indent=1)
        os.replace(tmp, TREE)
    finally:
        os.remove(REQUEST)
        _pending = False
    return GLib.SOURCE_REMOVE


def _call() -> bool:
    global _calling
    try:
        with open(CALL, encoding="utf-8") as handle:
            request = json.load(handle)
        os.remove(CALL)
        windows = [w for w in Gtk.Window.list_toplevels() if type(w).__name__ == "MainWindow"]
        # "on": the window showing that project; a method starting with "app." runs on the application.
        on = request.get("on")
        window: Any = next(w for w in windows if on is None or getattr(w, "project_id", None) == on)
        target: Any = window.get_application() if request["method"].startswith("app.") else window
        method = request["method"].removeprefix("app.")
        for part in method.split("."):
            target = getattr(target, part)
        result = target(*request.get("args", []), **request.get("kwargs", {}))
        answer = {
            "ok": True,
            "result": result if isinstance(result, (str, int, float, bool, type(None))) else repr(result),
        }
    except Exception as error:
        answer = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    tmp = CALL_OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(answer, handle)
    os.replace(tmp, CALL_OUT)
    _calling = False
    return GLib.SOURCE_REMOVE


def _poll() -> bool:
    global _pending
    global _calling
    if os.path.exists(CALL) and not _calling:
        _calling = True
        GLib.idle_add(_call)
    if os.path.exists(REQUEST) and not _pending:
        _pending = True
        # Below layout and paint: a widget mapped in this frame has no size until they run.
        GLib.idle_add(_answer, priority=GLib.PRIORITY_LOW)
    return GLib.SOURCE_CONTINUE


def main() -> int:
    GLib.timeout_add(300, _poll)
    from agent_tablet.app import main as app_main

    return app_main()


if __name__ == "__main__":
    sys.exit(main())
