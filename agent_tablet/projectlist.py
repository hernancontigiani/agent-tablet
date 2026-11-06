"""The current project's sessions: the user's groups first, then the sessions in no group.

The window decides what goes in (projects.rows) and each session's state; this widget only shows it
and says what the user picked.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango

from .i18n import _
from .models import SessionItem
from .projects import Group

STATES = ("working", "blocked", "done", "idle", "stopped")


class _Heading(Gtk.ListBoxRow):
    def __init__(self, group: Group | None) -> None:
        super().__init__(activatable=False, selectable=False)
        box = Gtk.Box(spacing=8)
        box.add_css_class("group-header")
        if group is not None:
            swatch = Gtk.Label()
            swatch.set_markup(f'<span foreground="{GLib.markup_escape_text(group.color)}">●</span>')
            box.append(swatch)
        label = Gtk.Label(label=group.name if group else _("No group"), xalign=0.0)
        label.add_css_class("caption-heading")
        label.add_css_class("dim-label")
        box.append(label)
        self.set_child(box)


class _SessionRow(Gtk.ListBoxRow):
    def __init__(self, item: SessionItem, folder: str, menu: Gio.MenuModel) -> None:
        super().__init__()
        self.item = item
        self.add_css_class("project-row")
        box = Gtk.Box(spacing=8, margin_top=6, margin_bottom=6, margin_start=10, margin_end=4)
        self.dot = Gtk.Box(valign=Gtk.Align.CENTER)
        self.dot.add_css_class("status-dot")
        box.append(self.dot)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        name = Gtk.Label(xalign=0.0, ellipsize=Pango.EllipsizeMode.END)
        name.add_css_class("heading")
        item.bind_property("display-name", name, "label", GObject.BindingFlags.SYNC_CREATE)
        text.append(name)
        if folder:
            folder_label = Gtk.Label(label=folder, xalign=0.0, ellipsize=Pango.EllipsizeMode.END)
            folder_label.add_css_class("dim-label")
            folder_label.add_css_class("caption")
            text.append(folder_label)
        box.append(text)

        self._menu = menu
        more = Gtk.Button(icon_name="view-more-symbolic", valign=Gtk.Align.CENTER)
        more.add_css_class("flat")
        more.set_tooltip_text(_("Actions for {name}").format(name=item.display_name))
        more.connect("clicked", lambda *_: self.show_menu(more))
        box.append(more)
        self.set_child(box)

        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("pressed", lambda *_: self.show_menu(more))
        self.add_controller(right)

    def show_menu(self, anchor: Gtk.Widget) -> None:
        # Built on each open and dropped on close, so one menu exists at a time.
        popover = Gtk.PopoverMenu.new_from_model(self._menu)
        popover.set_parent(anchor)
        popover.connect("closed", lambda p: GLib.idle_add(p.unparent))
        popover.popup()

    def set_state(self, state: str) -> None:
        for css in STATES:
            self.dot.remove_css_class(css)
        self.dot.add_css_class(state)
        self.dot.set_tooltip_text(state)


class ProjectList(Gtk.Box):
    __gsignals__: ClassVar[dict] = {
        "open": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list.add_css_class("navigation-sidebar")
        self._list.set_activate_on_single_click(False)  # a double click opens, as a file manager does
        self._list.connect("row-activated", self._on_activated)
        scrolled = Gtk.ScrolledWindow(child=self._list, vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._empty = Adw.StatusPage(icon_name="view-list-symbolic")
        self._empty.add_css_class("compact")
        add = Gtk.Button(label=_("Add session"), halign=Gtk.Align.CENTER)
        add.add_css_class("pill")
        add.add_css_class("suggested-action")
        add.set_action_name("win.add-session")
        self._empty.set_child(add)

        self._stack = Gtk.Stack(vexpand=True)
        self._stack.add_named(scrolled, "list")
        self._stack.add_named(self._empty, "empty")
        self.append(self._stack)
        self._rows: dict[str, _SessionRow] = {}

    def update(
        self,
        project_name: str,
        rows: list[tuple[Group | None, list[str]]],
        items: dict[str, SessionItem],
        folders: dict[str, str],
        menu_for: Callable[[str], Gio.MenuModel],
        states: dict[str, str],
    ) -> None:
        """rows: the project's sections; items: the sessions the store knows (others are skipped)."""
        self._list.remove_all()
        self._rows = {}
        shown = [(group, [sid for sid in ids if sid in items]) for group, ids in rows]
        shown = [(group, ids) for group, ids in shown if ids]
        has_groups = any(group is not None for group, _ids in shown)
        for group, ids in shown:
            if group is not None or has_groups:
                self._list.append(_Heading(group))
            for sid in ids:
                row = _SessionRow(items[sid], folders.get(sid, ""), menu_for(sid))
                row.set_state(states.get(sid, "stopped"))
                self._rows[sid] = row
                self._list.append(row)
        if not self._rows:
            self._empty.set_title(_("{name} has no sessions").format(name=project_name))
            self._empty.set_description(_("Add one Claude already knows, or start a new one in any folder."))
        self._stack.set_visible_child_name("list" if self._rows else "empty")

    def set_states(self, states: dict[str, str]) -> None:
        for sid, row in self._rows.items():
            row.set_state(states.get(sid, "stopped"))

    def _on_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if isinstance(row, _SessionRow):
            self.emit("open", row.item.session_id)
