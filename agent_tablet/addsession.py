"""The "Add session" dialog: put a session Claude already knows into the project, or start a new one."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from . import dialogs
from .i18n import _
from .models import SessionItem
from .projects import validate_new_session
from .providers import Provider, SessionOptions, available_providers
from .sidebar import SessionSidebar
from .store import SessionStore

EXISTING = "existing"
NEW = "new"


class AddSessionDialog(Adw.Dialog):
    def __init__(
        self,
        store: SessionStore,
        project_name: str,
        pick_label: Callable[[SessionItem], tuple[str, bool]],
        on_pick: Callable[[SessionItem], None],
        on_start: Callable[[str, Provider, str, SessionOptions | None], None],
        page: str = EXISTING,
        folder: str | None = None,
        provider: Provider | None = None,
        options: SessionOptions | None = None,
    ) -> None:
        super().__init__(title=_("Add a session to {name}").format(name=project_name))
        self.set_content_width(560)
        self.set_content_height(640)
        self._on_start = on_start
        self._options = options

        self.browser = SessionSidebar(store, pick_label=pick_label, on_pick=on_pick)

        self._stack = Adw.ViewStack()
        self._stack.add_titled_with_icon(
            self.browser, EXISTING, _("Existing"), "document-open-recent-symbolic"
        )
        self._stack.add_titled_with_icon(
            self._new_page(store, folder, provider), NEW, _("New"), "list-add-symbolic"
        )
        self._stack.set_visible_child_name(page)

        switcher = Adw.ViewSwitcher(stack=self._stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header = Adw.HeaderBar(title_widget=switcher)
        view = Adw.ToolbarView(content=self._stack)
        view.add_top_bar(header)
        self.set_child(view)

    # -- the "New" page -------------------------------------------------------------------

    def _new_page(self, store: SessionStore, folder: str | None, provider: Provider | None) -> Gtk.Widget:
        self._name = Adw.EntryRow(title=_("Name"))
        self._name.connect("entry-activated", lambda *_: self._start())

        known = sorted({s.cwd for s in store.sessions.values() if s.cwd})
        self._folders: list[str] = known
        if folder and folder not in self._folders:
            self._folders.insert(0, folder)
        self._folder = Adw.ComboRow(title=_("Folder"))
        self._folder.set_model(Gtk.StringList.new([*self._folders, _("Another folder…")]))
        if folder:
            self._folder.set_selected(self._folders.index(folder))
        self._folder.connect("notify::selected", self._on_folder_selected)

        self._providers = available_providers()
        self._provider = Adw.ComboRow(title=_("Agent"))
        self._provider.set_model(Gtk.StringList.new([p.name for p in self._providers]))
        if provider is not None and provider in self._providers:
            self._provider.set_selected(self._providers.index(provider))
        self._provider.set_visible(len(self._providers) > 1)

        group = Adw.PreferencesGroup(
            description=_("The name is Claude's own: sessions find each other by it.")
        )
        group.add(self._name)
        group.add(self._folder)
        group.add(self._provider)

        self._error = Gtk.Label(xalign=0.0, wrap=True, visible=False)
        self._error.add_css_class("error")

        start = Gtk.Button(label=_("Start session"), halign=Gtk.Align.END)
        start.add_css_class("suggested-action")
        start.add_css_class("pill")
        start.connect("clicked", lambda *_: self._start())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(18)
        box.append(group)
        box.append(self._error)
        box.append(start)
        return box

    def _on_folder_selected(self, row: Adw.ComboRow, _pspec) -> None:
        if row.get_selected() != len(self._folders):  # not "Another folder…"
            return
        chooser = Gtk.FileDialog(title=_("Choose a folder"))
        root = self.get_root()
        chooser.select_folder(root if isinstance(root, Gtk.Window) else None, None, self._on_folder_chosen)

    def _on_folder_chosen(self, chooser: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = chooser.select_folder_finish(result)
        except GLib.Error:
            self._folder.set_selected(0 if self._folders else Gtk.INVALID_LIST_POSITION)
            return
        path = dialogs.require_local_path(gfile, self, _("Choose a local folder")) if gfile else None
        if path is None:
            return
        if path not in self._folders:
            self._folders.insert(0, path)
            self._folder.set_model(Gtk.StringList.new([*self._folders, _("Another folder…")]))
        self._folder.set_selected(self._folders.index(path))

    def _start(self) -> None:
        index = self._folder.get_selected()
        folder = self._folders[index] if 0 <= index < len(self._folders) else ""
        name = self._name.get_text().strip()
        error = validate_new_session(name, folder)
        if error:
            self._error.set_label(error)
            self._error.set_visible(True)
            return
        provider = self._providers[self._provider.get_selected()] if self._providers else None
        if provider is None:
            return
        self.close()
        self._on_start(folder, provider, name, self._options)
