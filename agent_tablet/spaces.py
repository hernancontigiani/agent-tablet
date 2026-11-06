"""The tab strip: the tabs of the project a window shows.

The window owns the pages and pushes snapshots in via update(); the strip only renders and emits
what the user picked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk, Pango

from .context import ContextReading
from .contextring import ContextRing
from .i18n import _

_ELLIPSIZE_END = Pango.EllipsizeMode.END


@dataclass
class TabInfo:
    page: Adw.TabPage
    title: str
    space: str  # the id of the project the tab belongs to
    agent: str  # e.g. "claude", "cursor", "replay"
    status: str  # agent state: "working" | "blocked" | "done" | "idle"
    emoji: str = ""  # the tab's emoji, also the start of its title
    color: str = ""  # its sessions' group color, when they share one
    context: ContextReading | None = None  # the fullest context among its sessions


def _dot(status: str) -> Gtk.Widget:
    dot = Gtk.Box(valign=Gtk.Align.CENTER)
    dot.add_css_class("status-dot")
    if status:
        dot.add_css_class(status)
    return dot


class TabStrip(Gtk.Box):
    """Flat tab row for the current project, with a trailing "+"."""

    __gsignals__: ClassVar[dict] = {
        "select": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "close": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "menu": (GObject.SignalFlags.RUN_FIRST, None, (object, object)),  # page, widget
        "emoji": (GObject.SignalFlags.RUN_FIRST, None, (object,)),  # emoji clicked
    }

    def __init__(self) -> None:
        super().__init__(spacing=2)
        self.add_css_class("tab-strip")
        self._tabs = Gtk.Box(spacing=2)
        scrolled = Gtk.ScrolledWindow(child=self._tabs, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        scrolled.set_propagate_natural_height(True)
        self.append(scrolled)
        # shown while the Ctrl+B prefix waits for its key
        self._prefix = Gtk.Label(label="PREFIX", visible=False, valign=Gtk.Align.CENTER)
        self._prefix.add_css_class("prefix-pill")
        self.append(self._prefix)
        add = Gtk.Button(label="+")
        add.add_css_class("flat")
        add.set_tooltip_text(_("New session in this project"))
        add.set_action_name("win.new-in-space")
        self._tabs_add = add
        self._buttons: dict[Adw.TabPage, Gtk.Widget] = {}

    def set_prefix(self, active: bool) -> None:
        self._prefix.set_visible(active)

    def update(self, tabs: list[TabInfo], current: TabInfo | None) -> None:
        while (child := self._tabs.get_first_child()) is not None:
            self._tabs.remove(child)
        self._buttons = {}
        for tab in tabs:
            button = self._tab(tab, current is not None and current.page is tab.page)
            self._buttons[tab.page] = button
            self._tabs.append(button)
        self._tabs.append(self._tabs_add)

    def _on_emoji_pressed(self, gesture: Gtk.GestureClick, _n, _x, _y, page) -> None:
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)  # not a tab click
        self.emit("select", page)
        self.emit("emoji", page)

    def tab_bounds(self, page: Adw.TabPage) -> Gdk.Rectangle | None:
        """Where a page's tab sits, in strip coordinates (to anchor popovers)."""
        button = self._buttons.get(page)
        ok, rect = button.compute_bounds(self) if button is not None else (False, None)
        if not ok or rect is None:
            return None
        bounds = Gdk.Rectangle()
        bounds.x, bounds.y = int(rect.get_x()), int(rect.get_y())
        bounds.width, bounds.height = int(rect.get_width()), int(rect.get_height())
        return bounds

    def _tab(self, tab: TabInfo, selected: bool) -> Gtk.Widget:
        box = Gtk.Box(spacing=6)
        if tab.color:
            swatch = Gtk.Label()
            swatch.set_markup(f'<span foreground="{GLib.markup_escape_text(tab.color)}">●</span>')
            box.append(swatch)
        if tab.status != "idle":
            box.append(_dot(tab.status))
        if tab.context is not None:
            ring = ContextRing()
            ring.set_reading(tab.context)
            box.append(ring)
        title = tab.title
        if tab.emoji and title.startswith(tab.emoji):
            # the emoji is its own click target: it opens the picker
            emoji = Gtk.Label(label=tab.emoji)
            emoji.add_css_class("tab-emoji")
            emoji.set_tooltip_text(_("Change emoji"))
            emoji.set_cursor_from_name("pointer")
            click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
            click.connect("pressed", self._on_emoji_pressed, tab.page)
            emoji.add_controller(click)
            box.append(emoji)
            title = title[len(tab.emoji) :].lstrip()
        box.append(Gtk.Label(label=title, max_width_chars=28, ellipsize=_ELLIPSIZE_END))
        button = Gtk.Button(child=box)
        button.add_css_class("flat")
        button.add_css_class("strip-tab")
        if selected:
            button.add_css_class("selected")
        button.set_tooltip_text(tab.page.get_tooltip())
        button.connect("clicked", lambda *_: self.emit("select", tab.page))

        middle = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle.connect("pressed", lambda *_: self.emit("close", tab.page))
        button.add_controller(middle)
        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("pressed", lambda *_: self.emit("menu", tab.page, button))
        button.add_controller(right)
        return button
