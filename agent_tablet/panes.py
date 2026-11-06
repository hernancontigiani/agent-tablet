"""Split panes inside a tab: at most two terminal panes, side by side or stacked.

The *primary* pane names the tab and carries its emoji; either pane may hold a session or a shell.
Closing one leaves the other, which becomes the primary.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .layout import MAX_PANES
from .terminal import TerminalTab

# focus_direction() names → (axis, sign)
_DIRECTIONS = {"left": (0, -1), "right": (0, 1), "up": (1, -1), "down": (1, 1)}


class PaneContainer(Gtk.Box):
    def __init__(self, primary: TerminalTab) -> None:
        super().__init__()
        self.primary = primary
        self._focused = primary
        self._zoomed = False
        self._watch(primary)
        self.append(primary)

    # -- tree --------------------------------------------------------------

    def panes(self) -> list[TerminalTab]:
        """Every terminal pane, in layout order."""

        def leaves(widget: Gtk.Widget | None) -> list[TerminalTab]:
            if isinstance(widget, TerminalTab):
                return [widget]
            if isinstance(widget, Gtk.Paned):
                return leaves(widget.get_start_child()) + leaves(widget.get_end_child())
            return []

        return leaves(self.get_first_child())

    @property
    def focused(self) -> TerminalTab:
        return self._focused if self._focused in self.panes() else self.primary

    def _replace(self, old: Gtk.Widget, new: Gtk.Widget) -> None:
        parent = old.get_parent()
        if parent is self:
            self.remove(old)
            self.append(new)
        elif isinstance(parent, Gtk.Paned):
            if parent.get_start_child() is old:
                parent.set_start_child(None)
                parent.set_start_child(new)
            else:
                parent.set_end_child(None)
                parent.set_end_child(new)

    def _watch(self, pane: TerminalTab) -> None:
        focus = Gtk.EventControllerFocus()
        focus.connect("enter", lambda *_: setattr(self, "_focused", pane))
        pane.terminal.add_controller(focus)  # pyright: ignore[reportAttributeAccessIssue]  # VTE's stubs lack GTK4's Widget API

    # -- operations -----------------------------------------------------------

    def split(self, pane: TerminalTab, orientation: Gtk.Orientation) -> bool:
        """Put `pane` next to the focused one: HORIZONTAL = side by side
        (herdr's split right), VERTICAL = stacked (split down). False when the tab is full."""
        if len(self.panes()) >= MAX_PANES:
            return False
        self.unzoom()
        target = self.focused
        paned = Gtk.Paned(orientation=orientation, wide_handle=False)
        self._replace(target, paned)  # target leaves the tree first
        paned.set_start_child(target)
        paned.set_end_child(pane)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        self._watch(pane)
        self._focused = pane

        def halve() -> bool:  # once allocated, split the space evenly
            size = paned.get_width() if orientation == Gtk.Orientation.HORIZONTAL else paned.get_height()
            if size > 0:
                paned.set_position(size // 2)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(halve)
        GLib.idle_add(pane.grab_terminal_focus)
        return True

    def toggle_orientation(self) -> None:
        paned = self.get_first_child()
        if isinstance(paned, Gtk.Paned):
            vertical = paned.get_orientation() == Gtk.Orientation.VERTICAL
            paned.set_orientation(Gtk.Orientation.HORIZONTAL if vertical else Gtk.Orientation.VERTICAL)

    def close(self, pane: TerminalTab) -> None:
        """Remove a pane of a split; its sibling takes the split's place, and becomes the primary
        if the primary left."""
        self.unzoom()
        paned = pane.get_parent()
        if not isinstance(paned, Gtk.Paned):
            return
        sibling = paned.get_end_child() if paned.get_start_child() is pane else paned.get_start_child()
        root = self.get_root()
        if root is not None:
            root.set_focus(None)  # the Paned objects to losing its focused child
        paned.set_start_child(None)
        paned.set_end_child(None)
        assert sibling is not None  # a split always holds two panes
        self._replace(paned, sibling)
        if pane is self.primary and isinstance(sibling, TerminalTab):
            self.primary = sibling
        self._focused = sibling if isinstance(sibling, TerminalTab) else self.panes()[0]
        GLib.idle_add(self.focused.grab_terminal_focus)

    def focus_direction(self, direction: str) -> None:
        """Move focus to the nearest pane on that side of the focused one."""
        axis, sign = _DIRECTIONS[direction]
        current = self._center(self.focused)
        best, best_distance = None, None
        for pane in self.panes():
            if pane is self.focused or not pane.get_visible():
                continue
            center = self._center(pane)
            ahead = (center[axis] - current[axis]) * sign
            if ahead <= 0:
                continue
            distance = ahead + abs(center[1 - axis] - current[1 - axis]) * 2
            if best_distance is None or distance < best_distance:
                best, best_distance = pane, distance
        if best is not None:
            best.grab_terminal_focus()

    def cycle(self, step: int) -> None:
        panes = self.panes()
        if len(panes) > 1:
            panes[(panes.index(self.focused) + step) % len(panes)].grab_terminal_focus()

    def _center(self, pane: TerminalTab) -> tuple[float, float]:
        ok, rect = pane.compute_bounds(self)
        if not ok:
            return (0.0, 0.0)
        return (rect.get_x() + rect.get_width() / 2, rect.get_y() + rect.get_height() / 2)

    # -- zoom -------------------------------------------------------------------

    def toggle_zoom(self) -> None:
        if self._zoomed:
            self.unzoom()
            return
        if len(self.panes()) < 2:
            return
        self._zoomed = True
        self._show_only(self.get_first_child(), self.focused)

    def unzoom(self) -> None:
        if self._zoomed:
            self._zoomed = False
            self._show_only(self.get_first_child(), None)

    def _show_only(self, widget: Gtk.Widget | None, keep: TerminalTab | None) -> bool:
        """Show only `keep` (None = everything); a split stays visible while
        any pane in it does. Returns whether `widget` is visible."""
        if widget is None:
            return False
        if isinstance(widget, Gtk.Paned):
            start = self._show_only(widget.get_start_child(), keep)
            end = self._show_only(widget.get_end_child(), keep)
            visible = start or end
        else:
            visible = keep is None or widget is keep
        widget.set_visible(visible)
        return visible
