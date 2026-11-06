"""Find widgets in a dumped tree by what they are, and turn them into page coordinates."""

from __future__ import annotations

_TEXT_KEYS = ("label", "text", "tooltip_text", "title", "placeholder_text")


def _matches(widget: dict, type: str | None, text: str | None, css: str | None) -> bool:
    if type is not None and widget["type"] != type:
        return False
    if text is not None and text not in (widget.get(key) for key in _TEXT_KEYS):
        return False
    if css is not None and css not in widget.get("css", []):
        return False
    return "box" in widget


def find_all(
    tree: list[dict],
    *,
    type: str | None = None,
    text: str | None = None,
    css: str | None = None,
    window: str | None = None,
) -> list[tuple[dict, dict]]:
    return [
        (win, widget)
        for win in tree
        if window is None or win["title"] == window
        for widget in win["widgets"]
        if _matches(widget, type, text, css)
    ]


def _summary(widget: dict) -> str:
    texts = [widget[key] for key in _TEXT_KEYS if key in widget]
    return f"{widget['type']} {texts} at {widget.get('box')}"


def find(tree: list[dict], **match) -> tuple[dict, dict]:
    """Exactly one match, or an error that lists what was found instead."""
    found = find_all(tree, **match)
    if len(found) == 1:
        return found[0]
    if not found:
        windows = [win["title"] for win in tree]
        raise LookupError(f"no widget matches {match} in windows {windows}")
    candidates = "\n  ".join(_summary(widget) for _win, widget in found)
    raise LookupError(f"{len(found)} widgets match {match}; narrow it:\n  {candidates}")


def native_origin(native: dict, surfaces: list[dict]) -> tuple[float, float]:
    """Page coordinates of a native's (0, 0) — a window or a popover: its Broadway surface plus the
    shadow offset. A surface is matched by its content offset and its width (offset on both sides).
    """
    offset_x, offset_y = native["surface_offset"]
    width = native["size"][0]
    same = [
        s
        for s in surfaces
        if s["offset"] == [offset_x, offset_y] and abs(s["width"] - 2 * offset_x - width) <= 2
    ]
    if len(same) != 1:
        raise LookupError(f"{len(same)} Broadway surfaces fit {native['type']} {native['size']}: {surfaces}")
    return same[0]["x"] + offset_x, same[0]["y"] + offset_y


def page_point(window: dict, widget: dict, surfaces: list[dict]) -> tuple[float, float]:
    return click_point(native_origin(window["natives"][widget["native"]], surfaces), widget["box"])


def click_point(origin: tuple[float, float], box: list[int]) -> tuple[float, float]:
    x, y, width, height = box
    return origin[0] + x + width / 2, origin[1] + y + height / 2
