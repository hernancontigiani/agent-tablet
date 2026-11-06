"""The project dropdown at the top of the sidebar: switch, create, rename and delete projects."""

from __future__ import annotations

from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, GObject, Gtk, Pango

from .i18n import _
from .projects import Projects


def _badge(count: int) -> Gtk.Label:
    badge = Gtk.Label(label=str(count), valign=Gtk.Align.CENTER)
    badge.add_css_class("blocked-badge")
    badge.set_tooltip_text(_("Sessions waiting for you"))
    return badge


class ProjectBar(Gtk.MenuButton):
    __gsignals__: ClassVar[dict] = {
        "select": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "create": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "rename": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "delete": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self) -> None:
        super().__init__(hexpand=True)
        self.add_css_class("project-bar")
        self.set_tooltip_text(_("Projects"))
        face = Gtk.Box(spacing=6)
        self._name = Gtk.Label(xalign=0.0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        self._name.add_css_class("heading")
        face.append(self._name)
        self._face_badge = _badge(0)
        face.append(self._face_badge)
        face.append(Gtk.Image.new_from_icon_name("pan-down-symbolic"))
        self.set_child(face)

        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list.add_css_class("navigation-sidebar")
        self._list.connect("row-activated", self._on_activated)

        self._entry = Gtk.Entry(placeholder_text=_("New project name"), hexpand=True)
        self._entry.connect("activate", lambda *_: self._create())
        create = Gtk.Button(label=_("Create"))
        create.add_css_class("suggested-action")
        create.connect("clicked", lambda *_: self._create())
        new_row = Gtk.Box(spacing=6)
        new_row.append(self._entry)
        new_row.append(create)

        self._error = Gtk.Label(xalign=0.0, wrap=True, visible=False)
        self._error.add_css_class("error")

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        body.set_size_request(280, -1)
        body.append(self._list)
        body.append(Gtk.Separator())
        body.append(new_row)
        body.append(self._error)
        popover = Gtk.Popover(child=body)
        popover.connect("closed", lambda *_: self._error.set_visible(False))
        self.set_popover(popover)

    def update(
        self, projects: Projects, current: str, blocked: dict[str, int], elsewhere: set[str], others: int
    ) -> None:
        """blocked: sessions waiting per project; elsewhere: projects open in another window;
        others: sessions waiting in every project but this one."""
        shown = projects.get(current)
        self._name.set_label(shown.name)
        self._face_badge.set_label(str(others))
        self._face_badge.set_visible(others > 0)

        self._list.remove_all()
        for project in projects.projects:
            row = Gtk.ListBoxRow()
            row.project_id = project.id  # pyright: ignore[reportAttributeAccessIssue]
            box = Gtk.Box(spacing=6, margin_start=4, margin_end=4)
            mark = Gtk.Image.new_from_icon_name("object-select-symbolic")
            mark.set_opacity(1.0 if project.id == current else 0.0)
            box.append(mark)
            name = Gtk.Label(label=project.name, xalign=0.0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
            box.append(name)
            if blocked.get(project.id):
                box.append(_badge(blocked[project.id]))
            if project.id in elsewhere:
                where = Gtk.Label(label=_("open in another window"))
                where.add_css_class("dim-label")
                where.add_css_class("caption")
                box.append(where)
            count = Gtk.Label(label=str(len(project.members)))
            count.add_css_class("dim-label")
            count.set_tooltip_text(_("Sessions in this project"))
            box.append(count)
            for icon, tip, signal in (
                ("document-edit-symbolic", _("Rename project"), "rename"),
                ("user-trash-symbolic", _("Delete project"), "delete"),
            ):
                button = Gtk.Button(icon_name=icon, valign=Gtk.Align.CENTER)
                button.add_css_class("flat")
                button.set_tooltip_text(tip)
                button.connect("clicked", self._on_row_button, signal, project.id)
                box.append(button)
            row.set_child(box)
            self._list.append(row)

    def show_error(self, text: str) -> None:
        self._error.set_label(text)
        self._error.set_visible(True)

    def _on_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        self.popdown()
        self.emit("select", row.project_id)  # pyright: ignore[reportAttributeAccessIssue]

    def _on_row_button(self, _button: Gtk.Button, signal: str, project_id: str) -> None:
        self.popdown()
        # after the popover has closed: the dialog that follows takes the focus
        GLib.idle_add(lambda: self.emit(signal, project_id) and False)

    def _create(self) -> None:
        name = self._entry.get_text()
        self._error.set_visible(False)
        self.emit("create", name)
        if not self._error.get_visible():
            self._entry.set_text("")
            self.popdown()
