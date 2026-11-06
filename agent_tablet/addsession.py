"""The "Add session" dialog: put a session Claude already knows into the project, or start a new one."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, Pango

from . import dialogs
from .i18n import _
from .models import SessionItem
from .projects import validate_new_session
from .providers import Provider, SessionOptions, available_providers
from .sessions import Session
from .sidebar import SessionSidebar
from .store import SessionStore

EXISTING = "existing"
NEW = "new"


def folder_parts(path: str) -> tuple[str, str]:
    """A folder's name, and where it is with the home folder as "~": full paths cut at the end all
    start alike, so the name goes first."""
    folder = Path(path)
    home = str(Path.home())
    parent = str(folder.parent)
    if parent == home or parent.startswith(home + "/"):
        parent = "~" + parent[len(home) :]
    return (folder.name, parent) if folder.name else (path, "")


def recent_folders(sessions: Iterable[Session]) -> list[str]:
    """The folders sessions ran in, the most recently used first."""
    latest: dict[str, float] = {}
    for session in sessions:
        if session.cwd:
            latest[session.cwd] = max(latest.get(session.cwd, 0.0), session.mtime)
    return sorted(latest, key=lambda folder: latest[folder], reverse=True)


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
        """Two steps: pick the folder from a list that filters as you type, then name the session."""
        self._folder = ""
        self._folders = recent_folders(store.sessions.values())

        # -- step 1: the folder ------------------------------------------------------------
        self._folder_search = Gtk.SearchEntry(placeholder_text=_("Search folders…"), hexpand=True)
        self._folder_search.connect("search-changed", lambda *_: self._folder_list.invalidate_filter())
        self._folder_search.connect("activate", lambda *_: self._pick_first_shown())
        self._folder_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._folder_list.add_css_class("navigation-sidebar")
        self._folder_list.set_filter_func(self._folder_shown)
        self._folder_list.connect("row-activated", self._on_folder_row)
        for path in self._folders:
            self._folder_list.append(_FolderRow(path))
        self._folder_list.append(_FolderRow(None))  # "Another folder…", always shown
        scrolled = Gtk.ScrolledWindow(child=self._folder_list, vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        pick = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        _margins(pick, 12)
        pick.append(self._folder_search)
        pick.append(scrolled)

        # -- step 2: the name --------------------------------------------------------------
        self._chosen = Adw.ActionRow(title="", subtitle="")
        change = Gtk.Button(label=_("Change"), valign=Gtk.Align.CENTER)
        change.add_css_class("flat")
        change.connect("clicked", lambda *_: self._steps.set_visible_child_name("pick"))
        self._chosen.add_suffix(change)
        self._chosen.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))

        self._name = Adw.EntryRow(title=_("Name"))
        self._name.connect("entry-activated", lambda *_: self._start())

        self._providers = available_providers()
        self._provider = Adw.ComboRow(title=_("Agent"))
        self._provider.set_model(Gtk.StringList.new([p.name for p in self._providers]))
        if provider is not None and provider in self._providers:
            self._provider.set_selected(self._providers.index(provider))
        self._provider.set_visible(len(self._providers) > 1)

        group = Adw.PreferencesGroup(
            description=_("The name is Claude's own: sessions find each other by it.")
        )
        group.add(self._chosen)
        group.add(self._name)
        group.add(self._provider)

        self._error = Gtk.Label(xalign=0.0, wrap=True, visible=False)
        self._error.add_css_class("error")

        start = Gtk.Button(label=_("Start session"), halign=Gtk.Align.END)
        start.add_css_class("suggested-action")
        start.add_css_class("pill")
        start.connect("clicked", lambda *_: self._start())

        name = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        _margins(name, 18)
        name.append(group)
        name.append(self._error)
        name.append(start)

        self._steps = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._steps.add_named(pick, "pick")
        self._steps.add_named(name, "name")
        if folder:
            self._choose(folder)
        return self._steps

    def _folder_shown(self, row: Gtk.ListBoxRow) -> bool:
        query = self._folder_search.get_text().strip().lower()
        return not query or not isinstance(row, _FolderRow) or row.path is None or query in row.path.lower()

    def _pick_first_shown(self) -> None:
        row = next(
            (
                r
                for r in _rows(self._folder_list)
                if isinstance(r, _FolderRow) and r.path and self._folder_shown(r)
            ),
            None,
        )
        if row is not None and row.path:
            self._choose(row.path)

    def _on_folder_row(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if not isinstance(row, _FolderRow):
            return
        if row.path is not None:
            self._choose(row.path)
            return
        chooser = Gtk.FileDialog(title=_("Choose a folder"))
        root = self.get_root()
        chooser.select_folder(root if isinstance(root, Gtk.Window) else None, None, self._on_folder_chosen)

    def _on_folder_chosen(self, chooser: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = chooser.select_folder_finish(result)
        except GLib.Error:
            return  # cancelled: the list stays
        path = dialogs.require_local_path(gfile, self, _("Choose a local folder")) if gfile else None
        if path is not None:
            self._choose(path)

    def _choose(self, path: str) -> None:
        self._folder = path
        name, parent = folder_parts(path)
        self._chosen.set_title(GLib.markup_escape_text(name))
        self._chosen.set_subtitle(GLib.markup_escape_text(parent))
        self._error.set_visible(False)
        self._steps.set_visible_child_name("name")
        self._name.grab_focus()

    def _start(self) -> None:
        name = self._name.get_text().strip()
        error = validate_new_session(name, self._folder)
        if error:
            self._error.set_label(error)
            self._error.set_visible(True)
            return
        provider = self._providers[self._provider.get_selected()] if self._providers else None
        if provider is None:
            return
        self.close()
        self._on_start(self._folder, provider, name, self._options)


class _FolderRow(Gtk.ListBoxRow):
    """A folder by its name, with where it is below; None is "Another folder…"."""

    def __init__(self, path: str | None) -> None:
        super().__init__()
        self.path = path
        box = Gtk.Box(spacing=10, margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
        box.append(Gtk.Image.new_from_icon_name("folder-symbolic" if path else "folder-open-symbolic"))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        if path is None:
            text.append(Gtk.Label(label=_("Another folder…"), xalign=0.0))
        else:
            name, parent = folder_parts(path)
            title = Gtk.Label(label=name, xalign=0.0, ellipsize=Pango.EllipsizeMode.END)
            title.add_css_class("heading")
            where = Gtk.Label(label=parent, xalign=0.0, ellipsize=Pango.EllipsizeMode.START)
            where.add_css_class("dim-label")
            where.add_css_class("caption")
            text.append(title)
            text.append(where)
        box.append(text)
        self.set_child(box)


def _margins(box: Gtk.Box, size: int) -> None:
    for side in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{side}")(size)


def _rows(listbox: Gtk.ListBox) -> list[Gtk.ListBoxRow]:
    rows, child = [], listbox.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.ListBoxRow):
            rows.append(child)
        child = child.get_next_sibling()
    return rows
