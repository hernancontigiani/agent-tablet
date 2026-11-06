"""A small ring that fills with a session's context use: green, yellow from 60 %, red from 80 %.
The exact figure is in its tooltip; an estimate is drawn faint and says so. No reading, no ring."""

from __future__ import annotations

import math

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .context import ContextReading
from .i18n import _

WARN_AT = 60
FULL_AT = 80
SIZE = 14
_COLORS = {"ok": (0.40, 0.75, 0.45), "warn": (0.95, 0.75, 0.25), "full": (0.92, 0.33, 0.33)}


def level(percentage: float) -> str:
    if percentage >= FULL_AT:
        return "full"
    if percentage >= WARN_AT:
        return "warn"
    return "ok"


def _window_label(window: int) -> str:
    return f"{window // 1_000_000}M" if window >= 1_000_000 else f"{window // 1000}k"


def tooltip(reading: ContextReading) -> str:
    values = {"pct": f"{reading.percentage:.0f}", "window": _window_label(reading.window)}
    if reading.source == "estimate":
        return _("~{pct}% of {window} (estimate)").format(**values)
    return _("{pct}% of {window}").format(**values)


class ContextRing(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__(content_width=SIZE, content_height=SIZE, valign=Gtk.Align.CENTER)
        self._reading: ContextReading | None = None
        self.set_draw_func(self._draw)
        self.set_visible(False)

    def set_reading(self, reading: ContextReading | None) -> None:
        self._reading = reading
        self.set_visible(reading is not None)
        self.set_tooltip_text(tooltip(reading) if reading is not None else None)
        self.queue_draw()

    def _draw(self, _area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        reading = self._reading
        if reading is None:
            return
        red, green, blue = _COLORS[level(reading.percentage)]
        alpha = 0.45 if reading.source == "estimate" else 1.0
        centre_x, centre_y = width / 2, height / 2
        radius = min(width, height) / 2 - 1.5
        cr.set_line_width(2.5)
        cr.set_source_rgba(red, green, blue, 0.25 * alpha)
        cr.arc(centre_x, centre_y, radius, 0, 2 * math.pi)
        cr.stroke()
        fraction = max(0.0, min(reading.percentage, 100.0)) / 100
        cr.set_source_rgba(red, green, blue, alpha)
        cr.arc(centre_x, centre_y, radius, -math.pi / 2, -math.pi / 2 + 2 * math.pi * fraction)
        cr.stroke()
