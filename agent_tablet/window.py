"""Main window: composes the session sidebar with the tabbed terminal area."""

from __future__ import annotations

import shutil
import subprocess
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from . import __version__, dialogs, themes
from .addsession import EXISTING, NEW, AddSessionDialog
from .agentstate import rollup
from .chatsessionview import ChatSessionTab
from .context import ContextModel, ContextReading
from .i18n import _
from .layout import MAX_PANES, Orientation, TabLayout, WindowLayout
from .models import SessionItem
from .panes import PaneContainer
from .prefs import PreferencesDialog
from .projectbar import ProjectBar
from .projectlist import ProjectList
from .projects import ProjectError, blocked_elsewhere, folder_labels, joins_project
from .providers import Provider, SessionOptions, available_providers, get_provider
from .replayview import ReplayTab
from .sessions import Session, export_markdown, session_from_file
from .spaces import TabInfo, TabStrip
from .state import AppState
from .store import SessionStore
from .switcher import QuickSwitcher, SwitchEntry
from .terminal import TerminalTab
from .usagewindow import UsageWindow

_GHOSTTY = shutil.which("ghostty")

# keys that don't end the Ctrl+B prefix by themselves
_MODIFIER_KEYS = {
    Gdk.KEY_Shift_L,
    Gdk.KEY_Shift_R,
    Gdk.KEY_Control_L,
    Gdk.KEY_Control_R,
    Gdk.KEY_Alt_L,
    Gdk.KEY_Alt_R,
    Gdk.KEY_Super_L,
    Gdk.KEY_Super_R,
    Gdk.KEY_ISO_Level3_Shift,
    Gdk.KEY_Caps_Lock,
}


def _add_remove_button(chooser: Gtk.EmojiChooser, on_remove) -> None:
    """Put a "remove emoji" button at the end of the picker's search bar.
    ponytail: reaches into GtkEmojiChooser's internals (the .emoji-searchbar
    box); if GTK changes them the button just doesn't appear — the tab menu's
    "Remove emoji" still works."""

    def find(widget: Gtk.Widget) -> Gtk.Widget | None:
        if "emoji-searchbar" in widget.get_css_classes():
            return widget
        child = widget.get_first_child()
        while child is not None:
            if (found := find(child)) is not None:
                return found
            child = child.get_next_sibling()
        return None

    bar = find(chooser)
    if not isinstance(bar, Gtk.Box):
        return
    button = Gtk.Button(icon_name="edit-clear-symbolic", valign=Gtk.Align.CENTER)
    button.add_css_class("flat")
    button.set_tooltip_text(_("Remove emoji"))
    button.connect("clicked", lambda *_: (on_remove(), chooser.popdown()))
    bar.append(button)


class _Host(Protocol):
    """What a window asks of the application about the other windows."""

    def windows(self) -> list[MainWindow]: ...
    def save_layout(self) -> None: ...
    def window_closing(self, window: MainWindow) -> None: ...
    def window_holding(self, project_id: str, but: MainWindow | None = None) -> MainWindow | None: ...
    def held_elsewhere(self, window: MainWindow) -> set[str]: ...
    def all_states(self) -> dict[str, str]: ...


@dataclass
class _Joining:
    """A tab whose session joins `project_id` once Claude has a typed message for it."""

    project_id: str
    tab: TerminalTab
    page: Adw.TabPage
    closed: bool = False


class MainWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        state: AppState,
        store: SessionStore,
        project_id: str | None = None,
        context: ContextModel | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        # One model per app, shared by its windows; a window built alone (a test) makes its own.
        self.context = context if context is not None else ContextModel()
        context_handler = self.context.connect("changed", self._on_context_changed)
        # The model outlives a closed window; a handler left behind would call into a dead one.
        self.connect("destroy", lambda *_: self.context.disconnect(context_handler))
        self.set_title("Agent Tablet")
        self.set_icon_name("io.github.hernancontigiani.AgentTablet")
        self.set_default_size(1280, 800)

        self.state = state
        self.store = store
        self._pages: dict[str, Adw.TabPage] = {}  # session_id -> open tab
        self._confirmed_closes: set[Adw.TabPage] = set()
        self._closing_pages: dict[Adw.TabPage, int] = {}  # graceful close in progress -> attempts
        self._menu_page: Adw.TabPage | None = None
        self._base_titles: dict[Adw.TabPage, str] = {}  # fork/new tab title without emoji
        self._page_state: dict[Adw.TabPage, str] = {}  # working | blocked | done | idle
        self._switcher: QuickSwitcher | None = None
        # page -> (space folder, agent label); a space = folder with open tabs
        self._page_space: dict[Adw.TabPage, tuple[str, str]] = {}
        self._space_last: dict[str, Adw.TabPage] = {}  # last selected tab per space
        self._spaces_refresh_source: int | None = None
        self._joining: list[_Joining] = []
        self._pane_state: dict[TerminalTab, str] = {}  # working | blocked | done | idle, per pane
        self._moving: set[Adw.TabPage] = set()  # pages closed because their pane moved to another tab
        self._project_id = project_id or state.projects.current  # the project this window shows
        self._layout_save_source: int | None = None
        self._closing_confirmed = False
        self.connect("close-request", self._on_close_request)
        store.connect("refreshed", self._on_store_refreshed)

        self._prefix = False  # Ctrl+B pressed, waiting for the command key
        self._install_actions()
        self._install_shortcuts()

        # --- content pane: header + tab bar + tab view ---
        self.tab_view = Adw.TabView()
        # tab switching is per space (our next/prev actions), not global
        self.tab_view.set_shortcuts(Adw.TabViewShortcuts.NONE)
        self.tab_view.connect("notify::n-pages", lambda *_: self._queue_spaces_refresh())
        self.connect("notify::is-active", self._mark_seen)  # back to the window = seen
        self.tab_view.connect("close-page", self._on_close_page)
        self.tab_view.connect("notify::selected-page", self._on_selected_page_changed)

        self.tab_menu = tab_menu = Gio.Menu()
        tab_menu.append(_("Rename…"), "win.rename-tab")
        tab_menu.append(_("Set emoji…"), "win.set-tab-emoji")
        tab_menu.append(_("Remove emoji"), "win.remove-tab-emoji")
        tab_menu.append(_("Copy session ID"), "win.copy-tab-session-id")
        tab_menu.append(_("Swap the split's orientation"), "win.toggle-split")
        tab_menu.append(_("Close"), "win.close-menu-tab")

        # Shows only the current space's tabs (Adw.TabBar can't filter).
        # ponytail: no drag-to-reorder; add when someone misses it
        self.tab_strip = TabStrip()
        self.tab_strip.connect("select", lambda _s, page: self.tab_view.set_selected_page(page))
        self.tab_strip.connect("close", lambda _s, page: self.tab_view.close_page(page))
        self.tab_strip.connect("menu", self._on_tab_strip_menu)
        self.tab_strip.connect("emoji", lambda _s, page: self._set_tab_emoji(page))

        app_menu = Gio.Menu()
        app_menu.append(_("Open session file…"), "win.open-session-file")
        app_menu.append(_("Show hidden sessions"), "win.show-hidden")
        app_menu.append(_("MCP servers"), "win.mcp-servers")
        app_menu.append(_("Usage"), "win.usage")
        app_menu.append(_("Preferences"), "win.preferences")
        app_menu.append(_("About Agent Tablet"), "win.about")

        content_header = Adw.HeaderBar()
        self.sidebar_toggle = Gtk.ToggleButton(icon_name="sidebar-show-symbolic", active=True)
        self.sidebar_toggle.set_tooltip_text(_("Toggle sidebar (F9)"))
        content_header.pack_start(self.sidebar_toggle)

        new_menu = Gio.Menu()
        for provider in available_providers():
            new_menu.append(
                _("New {name} session…").format(name=provider.name),
                f"win.new-session-provider::{provider.id}",
            )
        for provider in available_providers():
            new_menu.append(
                _("New {name} session (advanced)…").format(name=provider.name),
                f"win.new-session-advanced::{provider.id}",
            )
            new_menu.append(
                _("Continue last {name} session…").format(name=provider.name),
                f"win.continue-session::{provider.id}",
            )
        for provider in available_providers():
            for variant in provider.chat_variants():  # native streaming chat
                if variant.label:
                    text = _("New {name} chat ({mode})").format(name=provider.name, mode=_(variant.label))
                else:
                    text = _("New {name} chat…").format(name=provider.name)
                new_menu.append(text, f"win.new-chat-provider::{provider.id}:{variant.key}")
        new_menu.append(_("New window"), "app.new-window")
        new_btn = Adw.SplitButton(icon_name="tab-new-symbolic")
        new_btn.set_tooltip_text(_("New session (Ctrl+Shift+T)"))
        new_btn.set_menu_model(new_menu)
        new_btn.connect("clicked", lambda *_: self._add_session(NEW))
        content_header.pack_start(new_btn)

        self.close_all_btn = Gtk.Button(icon_name="tab-close-symbolic", visible=False)
        self.close_all_btn.set_tooltip_text(_("Close all tabs"))
        self.close_all_btn.connect("clicked", lambda *_: self._close_all_tabs())
        content_header.pack_start(self.close_all_btn)
        self.tab_view.connect(
            "notify::n-pages",
            lambda *_: self.close_all_btn.set_visible(self.tab_view.get_n_pages() > 1),
        )

        placeholder = Adw.StatusPage(
            icon_name="utilities-terminal-symbolic",
            title=_("No session open"),
            description=_("Pick a session from the sidebar, or start a new one."),
        )

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(placeholder, "empty")
        self.content_stack.add_named(self.tab_view, "tabs")

        content_view = Adw.ToolbarView()
        content_view.add_top_bar(content_header)
        content_view.add_top_bar(self.tab_strip)
        self.toasts = Adw.ToastOverlay(child=self.content_stack)
        content_view.set_content(self.toasts)

        # --- sidebar: the project dropdown, its sessions, "Add session" ---
        self.project_bar = ProjectBar()
        self.project_bar.connect("select", lambda _b, pid: self._select_project(pid))
        self.project_bar.connect("create", lambda _b, name: self._create_project(name))
        self.project_bar.connect("rename", lambda _b, pid: self._rename_project(pid))
        self.project_bar.connect("delete", lambda _b, pid: self._delete_project(pid))
        menu_btn = Gtk.MenuButton(icon_name="emblem-system-symbolic", menu_model=app_menu)
        menu_btn.set_tooltip_text(_("Main menu"))
        side_header = Adw.HeaderBar()
        # The content header carries the window controls; without AdwOverlaySplitView
        # coordinating the two bars, hide them here so they are not duplicated.
        side_header.set_show_end_title_buttons(False)
        side_header.set_title_widget(self.project_bar)
        side_header.pack_end(menu_btn)

        self.project_list = ProjectList()
        self.project_list.connect("open", lambda _l, sid: self._open_member(sid))
        add_btn = Gtk.Button(
            label=_("Add session"), margin_top=6, margin_bottom=6, margin_start=8, margin_end=8
        )
        add_btn.set_action_name("win.add-session")

        side_view = Adw.ToolbarView(content=self.project_list, vexpand=True)
        side_view.add_top_bar(side_header)
        side_view.add_bottom_bar(add_btn)
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sidebar.add_css_class("app-sidebar")
        self.sidebar.append(side_view)

        self.sidebar.set_size_request(220, -1)  # minimum drag width
        self.split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.split.set_start_child(self.sidebar)
        self.split.set_end_child(content_view)
        self.split.set_resize_start_child(False)  # window resize grows the content, not the sidebar
        self.split.set_shrink_start_child(False)
        self.split.set_position(int(self.state.get_setting("sidebar_width")))
        self.split.connect("notify::position", self._schedule_save_sidebar_width)
        self.set_content(self.split)

        # Toggle button reflects (and controls) sidebar visibility.
        self._sidebar_width_save_source: int | None = None
        self.sidebar.bind_property(
            "visible",
            self.sidebar_toggle,
            "active",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )
        self.sidebar_toggle.connect("toggled", lambda b: self.sidebar.set_visible(b.get_active()))
        self._refresh_project()
        if state.projects.broken is not None:
            self.toasts.add_toast(
                Adw.Toast(
                    title=_(
                        "The projects file could not be read; it was kept as {name} and a new one started"
                    ).format(name=state.projects.broken.name),
                    timeout=0,
                )
            )

    # -- sidebar width persistence -------------------------------------------

    def _schedule_save_sidebar_width(self, *_args) -> None:
        if not self.sidebar.get_visible():
            return  # don't persist the collapsed position
        if self._sidebar_width_save_source is not None:
            GLib.source_remove(self._sidebar_width_save_source)
        self._sidebar_width_save_source = GLib.timeout_add(600, self._save_sidebar_width)

    def _save_sidebar_width(self) -> bool:
        self._sidebar_width_save_source = None
        position = self.split.get_position()
        if position >= 150:
            self.state.set_setting("sidebar_width", position)
        return GLib.SOURCE_REMOVE

    # -- actions / shortcuts -------------------------------------------------

    def _install_actions(self) -> None:
        plain = {
            "refresh": lambda *_: self.store.refresh(),
            "new-session": lambda *_: self._add_session(NEW),
            "add-session": lambda *_: self._add_session(EXISTING),
            "preferences": lambda *_: self._show_preferences(),
            "mcp-servers": lambda *_: dialogs.mcp_browser_dialog(self),
            "focus-search": lambda *_: self._add_session(EXISTING),
            "close-tab": lambda *_: self._close_current_tab(),
            "next-tab": lambda *_: self._cycle_space_tab(1),
            "prev-tab": lambda *_: self._cycle_space_tab(-1),
            "new-space": lambda *_: self._add_session(EXISTING),
            "new-in-space": lambda *_: self._add_session(NEW),
            "about": lambda *_: self._show_about(),
            "usage": lambda *_: self._show_usage(),
            "quick-switch": lambda *_: self._quick_switch(),
            "rename-tab": lambda *_: self._rename_tab(),
            "set-tab-emoji": lambda *_: self._set_tab_emoji(),
            "toggle-tab-emoji": lambda *_: self._toggle_tab_emoji(),
            "remove-tab-emoji": lambda *_: self._remove_tab_emoji(),
            "open-session-file": lambda *_: self._open_session_file(),
            "copy-tab-session-id": lambda *_: self._copy_tab_session_id(),
            "close-menu-tab": lambda *_: self._close_menu_tab(),
            "toggle-split": lambda *_: (panes := self._panes()) and panes.toggle_orientation(),
            "toggle-sidebar": lambda *_: self.sidebar.set_visible(not self.sidebar.get_visible()),
        }
        for name, callback in plain.items():
            action = Gio.SimpleAction(name=name)
            action.connect("activate", callback)
            self.add_action(action)

        per_session = {
            "new-session-provider": lambda _a, p: self._add_session(
                NEW, provider=get_provider(p.get_string())
            ),
            "new-chat-provider": lambda _a, p: self._new_chat_session_target(p.get_string()),
            "new-session-advanced": lambda _a, p: self._new_session_advanced(get_provider(p.get_string())),
            "continue-session": lambda _a, p: self._continue_session(get_provider(p.get_string())),
            "open-session": self._on_open_action,
            "fork-session": self._on_fork_action,
            "replay-session": self._on_replay_action,
            "resume-chat": self._on_resume_chat_action,
            "delete-session": self._on_delete_session,
            "open-ghostty": self._on_open_ghostty,
            "rename-session": self._on_rename_action,
            "copy-session-id": lambda _a, p: self.get_clipboard().set(p.get_string()),
            "reveal-transcript": self._on_reveal_transcript,
            "export-session": self._on_export_session,
            "session-details": self._on_session_details,
            "hide-session": self._on_hide_session,
            "trash-session": self._on_trash_session,
            "stop-session": lambda _a, p: self._stop_session(p.get_string()),
            "remove-from-project": lambda _a, p: self._remove_from_project(p.get_string()),
            "set-group": lambda _a, p: self._set_group(*p.get_string().split("\x1f", 1)),
            "new-group": lambda _a, p: self._new_group(p.get_string()),
            "open-beside": lambda _a, p: self._open_beside(p.get_string()),
        }
        for name, callback in per_session.items():
            action = Gio.SimpleAction(name=name, parameter_type=GLib.VariantType("s"))
            action.connect("activate", callback)
            self.add_action(action)

        show_hidden = Gio.SimpleAction.new_stateful("show-hidden", None, GLib.Variant.new_boolean(False))
        show_hidden.connect("change-state", self._on_show_hidden)
        self.add_action(show_hidden)

    def _install_shortcuts(self) -> None:
        controller = Gtk.ShortcutController()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        for trigger, action in (
            ("<Control><Shift>f", "win.focus-search"),
            ("<Control><Shift>t", "win.new-session"),
            ("<Control><Shift>w", "win.close-tab"),
            ("<Control>Page_Down", "win.next-tab"),
            ("<Control>Page_Up", "win.prev-tab"),
            ("<Control>Tab", "win.next-tab"),
            ("<Control><Shift>ISO_Left_Tab", "win.prev-tab"),
            ("<Control>comma", "win.preferences"),
            ("<Control><Shift>k", "win.quick-switch"),
            ("<Control><Shift>e", "win.toggle-tab-emoji"),
            ("<Control>period", "win.set-tab-emoji"),  # GNOME's emoji key
            ("F9", "win.toggle-sidebar"),
        ):
            controller.add_shortcut(
                Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(trigger), Gtk.NamedAction.new(action))
            )
        self.add_controller(controller)

        # herdr / tmux style prefix: Ctrl+B, then a key (see _prefix_keys)
        prefix = Gtk.EventControllerKey()
        prefix.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        prefix.connect("key-pressed", self._on_prefix_key)
        self.add_controller(prefix)

    # -- sidebar signal handlers -------------------------------------------------

    def _on_sidebar_open_many(self, _sidebar, items: list[SessionItem]) -> None:
        for item in items:
            self.open_session(item.session)

    def _on_sidebar_trash_many(self, _sidebar, items: list[SessionItem]) -> None:
        def do_trash() -> None:
            errors = []
            for item in items:
                error = self.store.trash(item.session_id)
                if error:
                    errors.append(f"{item.display_name}: {error}")
                    continue
                page = self._pages.get(item.session_id)
                if page is not None:
                    self.tab_view.close_page(page)
            if errors:
                dialogs.error_dialog(self, _("Some transcripts could not be trashed"), "\n".join(errors))

        dialogs.confirm_dialog(
            self,
            _("Move {n} transcript(s) to trash?").format(n=len(items)),
            _("The files are moved to the trash and can be restored."),
            _("Move to Trash"),
            do_trash,
        )

    # -- tabs --------------------------------------------------------------

    def open_session(self, session: Session, fork: bool = False) -> None:
        provider = get_provider(session.provider)
        fork = fork and provider.supports_fork
        if not fork:
            self._make_member(session.session_id)
            page = self._pages.get(session.session_id)
            if page is not None:
                self.tab_view.set_selected_page(page)
                return

        tab = TerminalTab(
            cwd=session.cwd,
            session_id=session.session_id,
            fork=fork,
            settings=self.state.settings,
            provider=provider,
            jsonl_path=None if fork else session.jsonl_path,
            new_id=str(uuid.uuid4()) if fork else None,
        )
        title = f"{self.store.display_name(session)} (fork)" if fork else self._tab_title(session)
        page = self._add_tab(tab, title, f"{session.project_name} — {session.session_id}")
        if fork:
            self._join_when_created(tab, page)
        else:
            self._pages[session.session_id] = page
            self._sync_status(session.session_id)

    def _tab_title(self, session: Session) -> str:
        """Tab title with the session's saved emoji prefix (tabs only)."""
        name = self.store.display_name(session)
        emoji = self.state.get_emoji(session.session_id)
        return f"{emoji} {name}" if emoji else name

    def _default_provider(self):
        """First installed agent (Claude when present), used by the quick button."""
        providers = available_providers()
        return providers[0] if providers else get_provider("claude")

    def _start_new_session(self, cwd: str, provider=None, options=None, name: str | None = None) -> None:
        provider = provider or self._default_provider()
        tab = TerminalTab(
            cwd=cwd,
            session_id=None,
            settings=self.state.settings,
            provider=provider,
            options=options,
            new_id=str(uuid.uuid4()),
            name=name,
        )
        page = self._add_tab(
            tab,
            name or GLib.path_get_basename(cwd),
            f"new {provider.name} session — {cwd}",
        )
        self._join_when_created(tab, page)

    # -- a new session joins the current project -------------------------------------

    def _join_when_created(self, tab: TerminalTab, page: Adw.TabPage) -> None:
        self._joining.append(_Joining(self.state.projects.current, tab, page))

    def _on_store_refreshed(self, _store, _order_changed: bool) -> None:
        self._join_created()
        self._refresh_project()

    def _join_created(self) -> None:
        projects = self.state.projects
        for joining in list(self._joining):
            session_id = joining.tab.transcript_id or joining.tab.new_id
            session = self.store.get_session(session_id) if session_id else None
            if session is not None and session_id and joins_project(session):
                target = joining.project_id
                if all(p.id != target for p in projects.projects):
                    target = projects.current  # its project was deleted meanwhile
                projects.add(target, session_id)
                self.state.save_projects()
                self._joining.remove(joining)
                if not joining.closed:
                    joining.tab.session_id = session_id
                    joining.tab.fork = False
                    self._pages[session_id] = joining.page
                    self._sync_status(session_id)
            elif joining.closed:
                self._joining.remove(joining)

    # -- projects --------------------------------------------------------------------------

    def _project_name(self, project_id: str) -> str:
        try:
            return self.state.projects.get(project_id).name
        except KeyError:
            return ""

    def _display(self, session_id: str) -> str:
        session = self.store.get_session(session_id)
        return self.store.display_name(session) if session else session_id[:8]

    def _session_states(self) -> dict[str, str]:
        states = {}
        for page in set(self._pages.values()):
            for pane in self._panes_of(page):
                if sid := self._pane_session(pane):
                    states[sid] = self._pane_state.get(pane, "idle")
        return states

    def _update_project_bar(self, states: dict[str, str]) -> None:
        app = self._app()
        elsewhere: set[str] = set()
        if app is not None:
            states = app.all_states()
            elsewhere = app.held_elsewhere(self)
        projects = self.state.projects
        blocked = {
            p.id: sum(1 for sid in p.members if states.get(sid) == "blocked") for p in projects.projects
        }
        others = blocked_elsewhere(projects, self._project_id, states)
        self.project_bar.update(projects, self._project_id, blocked, elsewhere, others)

    def _refresh_project(self) -> None:
        projects = self.state.projects
        project = projects.get(self._project_id)
        items = {sid: item for sid in project.members if (item := self.store.get_item(sid)) is not None}
        folders = folder_labels({sid: item.session.cwd for sid, item in items.items()})
        states = self._session_states()
        self.project_list.update(
            project.name, projects.rows(project.id), items, folders, self._menu_for, states
        )
        for sid, item in items.items():
            self.context.track(sid, item.session.jsonl_path)
            self.project_list.set_reading(sid, self.context.get(sid))
        self._update_project_bar(states)

    def _menu_for(self, session_id: str) -> Gio.Menu:
        def item(label: str, action: str, value: str = session_id) -> Gio.MenuItem:
            menu_item = Gio.MenuItem.new(label, None)
            menu_item.set_action_and_target_value(f"win.{action}", GLib.Variant("s", value))
            return menu_item

        run = Gio.Menu()
        run.append_item(item(_("Open"), "open-session"))
        run.append_item(item(_("Open beside the current tab"), "open-beside"))
        run.append_item(item(_("Stop"), "stop-session"))
        groups = Gio.Menu()
        for group in self.state.projects.get(self._project_id).groups:
            groups.append_item(item(group.name, "set-group", f"{session_id}\x1f{group.name}"))
        groups.append_item(item(_("No group"), "set-group", f"{session_id}\x1f"))
        groups.append_item(item(_("New group…"), "new-group"))
        run.append_submenu(_("Group"), groups)

        more = Gio.Menu()
        more.append_item(item(_("Rename…"), "rename-session"))
        more.append_item(item(_("Details…"), "session-details"))
        more.append_item(item(_("Replay…"), "replay-session"))
        more.append_item(item(_("Copy session ID"), "copy-session-id"))
        more.append_item(item(_("Export as Markdown…"), "export-session"))
        more.append_item(item(_("Reveal transcript"), "reveal-transcript"))

        leave = Gio.Menu()
        leave.append_item(item(_("Remove from project"), "remove-from-project"))

        menu = Gio.Menu()
        menu.append_section(None, run)
        menu.append_section(None, more)
        menu.append_section(None, leave)
        return menu

    def _open_member(self, session_id: str) -> None:
        session = self.store.get_session(session_id)
        if session is not None:
            self.open_session(session)

    def _make_member(self, session_id: str) -> None:
        """Opening a session puts it in a project: its own, shown first, or this one if it has none."""
        projects = self.state.projects
        owner = projects.owner(session_id)
        if owner is None:
            projects.add(self._project_id, session_id)
            self.state.save_projects()
            self._refresh_project()
        elif owner.id != self._project_id:
            self._select_project(owner.id)

    def _select_project(self, project_id: str) -> None:
        if project_id == self._project_id:
            return
        app = self._app()
        holder = app.window_holding(project_id, but=self) if app is not None else None
        if holder is not None:
            holder.present()
            return
        self._project_id = project_id
        self.state.projects.current = project_id
        self.state.save_projects()
        self._show_project_tabs()
        self._refresh_project()
        self._queue_spaces_refresh()

    def _show_project_tabs(self) -> None:
        page = self._space_last.get(self._project_id)
        if page is None or page not in self._page_space:
            page = next((p for p, (space, _a) in self._page_space.items() if space == self._project_id), None)
        if page is None:
            self.content_stack.set_visible_child_name("empty")
            return
        self.content_stack.set_visible_child_name("tabs")
        if self.tab_view.get_selected_page() is not page:
            self.tab_view.set_selected_page(page)

    def _create_project(self, name: str) -> None:
        try:
            project = self.state.projects.create(name)
        except ProjectError as error:
            self.project_bar.show_error(str(error))
            return
        self.state.save_projects()
        self._select_project(project.id)

    def _rename_project(self, project_id: str) -> None:
        def save(name: str) -> None:
            try:
                self.state.projects.rename(project_id, name)
            except ProjectError as error:
                dialogs.error_dialog(self, _("The project was not renamed"), str(error))
                return
            self.state.save_projects()
            self._refresh_project()

        dialogs.text_dialog(self, _("Rename project"), "", self._project_name(project_id), _("Name"), save)

    def _delete_project(self, project_id: str) -> None:
        projects = self.state.projects
        if len(projects.projects) == 1:
            dialogs.error_dialog(
                self, _("The project was not deleted"), _("The last project cannot be deleted.")
            )
            return
        project = projects.get(project_id)
        running = [sid for sid in project.members if sid in self._pages]
        body = _("Its sessions leave the list; their conversations stay in Claude.")
        if running:
            body += " " + _("{n} running session(s) will be stopped first.").format(n=len(running))

        def delete() -> None:
            for sid in running:
                self._stop_session(sid)
            for page, (space, _agent) in list(self._page_space.items()):
                if space == project_id and self._session_id_of(page) is None:
                    self.tab_view.close_page(page)  # its chat and replay tabs go with it
            projects.delete(project_id)
            if self._project_id == project_id:
                self._project_id = projects.projects[0].id
                projects.current = self._project_id
            self.state.save_projects()
            self._show_project_tabs()
            self._refresh_project()
            self._queue_spaces_refresh()

        dialogs.confirm_dialog(
            self, _("Delete “{name}”?").format(name=project.name), body, _("Delete"), delete
        )

    def _stop_session(self, session_id: str) -> None:
        page = self._pages.get(session_id)
        if page is None:
            return
        panes = self._panes_of(page)
        if len(panes) > 1:
            pane = next(p for p in panes if self._pane_session(p) == session_id)
            self._stop_pane(pane)
        else:
            self.tab_view.close_page(page)

    def _open_beside(self, session_id: str) -> None:
        """Put a session in the second pane of the current tab; one already open alone in its own
        tab moves here without stopping."""
        page = self.tab_view.get_selected_page()
        panes = self._panes()
        session = self.store.get_session(session_id)
        if (
            page is None
            or panes is None
            or session is None
            or self._page_space.get(page, (None,))[0] != self._project_id
        ):
            if session is not None:
                self.open_session(session)
            return
        owner = self.state.projects.owner(session_id)
        if owner is not None and owner.id != self._project_id:
            self.toasts.add_toast(
                Adw.Toast(title=_("It belongs to another project; add it here first"), timeout=4)
            )
            return
        if self._pages.get(session_id) is page:
            return
        if len(panes.panes()) >= MAX_PANES:
            self.toasts.add_toast(Adw.Toast(title=_("A tab holds two panes at most"), timeout=4))
            return
        self._make_member(session_id)
        existing = self._pages.get(session_id)
        if existing is not None:
            other = existing.get_child()
            if not isinstance(other, PaneContainer) or len(other.panes()) > 1:
                self.toasts.add_toast(Adw.Toast(title=_("It is already beside another session"), timeout=4))
                return
            pane = other.primary
            other.remove(pane)
            self._moving.add(existing)
            self.tab_view.close_page(existing)
        else:
            pane = TerminalTab(
                cwd=session.cwd,
                session_id=session_id,
                settings=self.state.settings,
                provider=get_provider(session.provider),
                jsonl_path=session.jsonl_path,
            )
            self._watch_pane(pane)
        panes.split(pane, Gtk.Orientation.HORIZONTAL)
        self._pages[session_id] = page
        self._sync_status(session_id)
        self._retitle(page)
        self._refresh_page_state(page)

    def _window_with_session(self, session_id: str) -> MainWindow | None:
        app = self._app()
        windows = app.windows() if app is not None else [self]
        return next((w for w in windows if session_id in w._pages), None)

    def _take_tab(self, other: MainWindow, session_id: str) -> bool:
        """Move a session's tab from another window into this one, without stopping it."""
        page = other._pages[session_id]
        if len(other._session_ids_of(page)) > 1:
            self.toasts.add_toast(Adw.Toast(title=_("It shares a tab with another session there"), timeout=4))
            return False
        panes = other._panes_of(page)
        states = other._forget_page(page)
        for pane in panes:
            pane.disconnect_by_func(other._on_pane_exited)
            pane.disconnect_by_func(other._on_pane_state)
        other.tab_view.transfer_page(page, self.tab_view, self.tab_view.get_n_pages())
        self._page_space[page] = (self._project_id, panes[0].provider.id if panes else "")
        self._pages[session_id] = page
        for pane in panes:
            self._watch_pane(pane)
            self._pane_state[pane] = states.get(pane, "idle")
        other._show_project_tabs()
        other._refresh_project()
        self.content_stack.set_visible_child_name("tabs")
        self.tab_view.set_selected_page(page)
        return True

    def _forget_page(self, page: Adw.TabPage) -> dict[TerminalTab, str]:
        """Drop what this window keeps about a page that leaves it; returns its panes' states."""
        states = {pane: self._pane_state.pop(pane, "idle") for pane in self._panes_of(page)}
        for session_id, open_page in list(self._pages.items()):
            if open_page is page:
                del self._pages[session_id]
        self._page_space.pop(page, None)
        self._page_state.pop(page, None)
        self._base_titles.pop(page, None)
        self._space_last = {k: v for k, v in self._space_last.items() if v is not page}
        return states

    def _retitle(self, page: Adw.TabPage) -> None:
        """A tab of two sessions is named after both."""
        sessions = [s for sid in self._session_ids_of(page) if (s := self.store.get_session(sid))]
        if len(sessions) > 1:
            page.set_title(" │ ".join(self.store.display_name(s) for s in sessions))
        elif len(sessions) == 1:
            page.set_title(self._tab_title(sessions[0]))

    def _remove_from_project(self, session_id: str) -> None:
        projects = self.state.projects
        owner = projects.owner(session_id)
        if owner is None:
            return

        def remove() -> None:
            self._stop_session(session_id)
            projects.remove(owner.id, session_id)
            self.state.save_projects()
            self._refresh_project()

        if session_id not in self._pages:
            remove()
            return
        dialogs.confirm_dialog(
            self,
            _("Remove “{name}” from the project?").format(name=self._display(session_id)),
            _("It is running, so it is stopped first. Its conversation stays in Claude."),
            _("Stop and remove"),
            remove,
        )

    def _set_group(self, session_id: str, group: str = "") -> None:
        self.state.projects.set_group(self._project_id, session_id, group or None)
        self.state.save_projects()
        self._refresh_project()

    def _new_group(self, session_id: str) -> None:
        def save(name: str) -> None:
            try:
                self.state.projects.new_group(self._project_id, name, session_id)
            except ProjectError as error:
                dialogs.error_dialog(self, _("The group was not created"), str(error))
                return
            self.state.save_projects()
            self._refresh_project()

        dialogs.text_dialog(
            self,
            _("New group"),
            _("Groups belong to this project; they never change a session's name."),
            "",
            _("Name"),
            save,
        )

    def _add_session(
        self,
        page: str,
        provider: Provider | None = None,
        folder: str | None = None,
        options: SessionOptions | None = None,
    ) -> None:
        projects = self.state.projects
        project = projects.get(self._project_id)

        def label(item: SessionItem) -> tuple[str, bool]:
            owner = projects.owner(item.session_id)
            if owner is None:
                return _("Add"), True
            if owner.id == self._project_id:
                return _("Added"), False
            return _("Move from {name}").format(name=owner.name), True

        def pick(item: SessionItem) -> None:
            holder = self._window_with_session(item.session_id)
            if holder is not None and holder is not self and not self._take_tab(holder, item.session_id):
                return
            previous = projects.add(self._project_id, item.session_id)
            open_page = self._pages.get(item.session_id)
            if previous is not None and open_page is not None:
                self._page_space[open_page] = (self._project_id, self._page_space[open_page][1])
            self.state.save_projects()
            self._refresh_project()
            self._queue_spaces_refresh()

        def start(cwd: str, chosen: Provider, name: str, chosen_options: SessionOptions | None) -> None:
            self.state.set_setting("new_session_dir", cwd)
            self._start_new_session(cwd, chosen, chosen_options, name)

        remembered = self.state.get_setting("new_session_dir")
        if folder is None and remembered and Path(remembered).is_dir():
            folder = remembered
        dialog = AddSessionDialog(
            self.store, project.name, label, pick, start, page, folder, provider, options
        )
        dialog.browser.connect("open-many", self._on_sidebar_open_many)
        dialog.browser.connect("trash-many", self._on_sidebar_trash_many)
        dialog.present(self)

    # -- advanced new session / continue -----------------------------------

    def _new_session_advanced(self, provider) -> None:
        self._adv_provider = provider or self._default_provider()
        dialog = Gtk.FileDialog(title=_("Choose project directory"))
        default = self.state.get_setting("new_session_dir")
        if default and Path(default).is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(default))
        dialog.select_folder(self, None, self._on_advanced_folder)

    def _on_advanced_folder(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        cwd = dialogs.require_local_path(folder, self, _("Choose a local folder"))
        if cwd is None:
            return
        self.state.set_setting("new_session_dir", cwd)
        provider = getattr(self, "_adv_provider", None) or self._default_provider()
        dialogs.new_session_options_dialog(
            self, provider, lambda opts: self._add_session(NEW, provider=provider, folder=cwd, options=opts)
        )

    def _continue_session(self, provider) -> None:
        self._cont_provider = provider or self._default_provider()
        dialog = Gtk.FileDialog(title=_("Choose project directory"))
        default = self.state.get_setting("new_session_dir")
        if default and Path(default).is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(default))
        dialog.select_folder(self, None, self._on_continue_folder)

    def _on_continue_folder(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        cwd = dialogs.require_local_path(folder, self, _("Choose a local folder"))
        if cwd is None:
            return
        self.state.set_setting("new_session_dir", cwd)
        provider = getattr(self, "_cont_provider", None) or self._default_provider()
        tab = TerminalTab(
            cwd=cwd,
            settings=self.state.settings,
            provider=provider,
            command_override=provider.continue_command(),
        )
        page = self._add_tab(tab, GLib.path_get_basename(cwd), f"continue {provider.name} — {cwd}")
        self._join_when_created(tab, page)

    def _append_page(self, tab: Gtk.Widget, title: str, tooltip: str, agent: str) -> Adw.TabPage:
        """Append a tab into the project this window shows and select it."""
        page = self.tab_view.append(tab)
        page.set_title(title)
        page.set_tooltip(tooltip)
        self._page_space[page] = (self._project_id, agent)
        page.connect("notify::title", lambda *_: self._queue_spaces_refresh())
        page.connect("notify::needs-attention", lambda *_: self._queue_spaces_refresh())
        self.tab_view.set_selected_page(page)
        self.content_stack.set_visible_child_name("tabs")
        return page

    def _add_tab(self, tab: TerminalTab, title: str, tooltip: str) -> Adw.TabPage:
        panes = PaneContainer(tab)  # splits live in here; `tab` stays the primary
        page = self._append_page(panes, title, tooltip, tab.provider.id)
        self._watch_pane(tab)
        GLib.idle_add(tab.grab_terminal_focus)
        return page

    # -- chat sessions (headless streaming) --------------------------------

    def _new_chat_session_target(self, target: str) -> None:
        provider_id, _, variant_key = target.partition(":")
        self._new_chat_session(get_provider(provider_id), variant_key)

    def _new_chat_session(self, provider, variant_key: str = "") -> None:
        self._new_chat_provider = provider
        self._new_chat_variant_key = variant_key
        dialog = Gtk.FileDialog(title=_("Choose project directory"))
        default = self.state.get_setting("new_session_dir")
        if default and Path(default).is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(default))
        dialog.select_folder(self, None, self._on_new_chat_folder)

    def _on_new_chat_folder(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return  # cancelled
        cwd = dialogs.require_local_path(folder, self, _("Choose a local folder"))
        if cwd is None:
            return
        self.state.set_setting("new_session_dir", cwd)
        self._start_new_chat_session(
            cwd,
            getattr(self, "_new_chat_provider", None),
            getattr(self, "_new_chat_variant_key", ""),
        )

    def _start_new_chat_session(self, cwd: str, provider=None, variant_key: str = "") -> None:
        provider = provider or self._default_provider()
        variants = provider.chat_variants()
        variant = provider.chat_variant(variant_key) or (variants[0] if variants else None)
        if variant is None:
            return
        tab = ChatSessionTab(cwd=cwd, provider=provider, variant=variant)
        self._append_page(
            tab,
            _("Chat — {dir}").format(dir=GLib.path_get_basename(cwd)),
            f"{provider.name} chat — {cwd}",
            f"{provider.id} chat",
        )

    def _on_resume_chat_action(self, _action, param: GLib.Variant) -> None:
        variant_key, _sep, session_id = param.get_string().partition(":")
        session = self.store.get_session(session_id)
        if session is None:
            return
        provider = get_provider(session.provider)
        variants = provider.chat_variants()
        variant = provider.chat_variant(variant_key) or (variants[0] if variants else None)
        if variant is None:
            return
        tab = ChatSessionTab(
            cwd=session.cwd, provider=provider, variant=variant, resume_session_id=session_id
        )
        self._append_page(
            tab,
            _("Chat — {name}").format(name=self.store.display_name(session)),
            f"{provider.name} chat — {session.session_id}",
            f"{provider.id} chat",
        )

    # -- session replay ----------------------------------------------------

    def _on_replay_action(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is not None:
            self._open_replay(session)

    def _open_replay(self, session: Session) -> None:
        tab = ReplayTab(session, session.provider)
        self._append_page(
            tab,
            _("Replay — {name}").format(name=self.store.display_name(session)),
            f"replay — {session.project_name} — {session.session_id}",
            "replay",
        )

    def _close_current_tab(self) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _close_all_tabs(self) -> None:
        pages = [self.tab_view.get_nth_page(i) for i in range(self.tab_view.get_n_pages())]
        for page in pages:
            self.tab_view.close_page(page)

    def _close_confirmed(self, page: Adw.TabPage) -> None:
        """Force-close (terminate the child) — the graceful-close fallback."""
        self._confirmed_closes.add(page)
        self.tab_view.close_page(page)

    def _graceful_close(self, page: Adw.TabPage) -> None:
        """Ask every agent in the tab to exit cleanly (e.g. Claude's /exit), then close once the
        shells return. Falls back to a force-close after a timeout. Agents with no
        clean-exit command (e.g. Cursor) are force-closed directly."""
        running = [pane for pane in self._panes_of(page) if pane.has_running_command()]
        if not running or any(not pane.provider.graceful_exit() for pane in running):
            self._close_confirmed(page)
            return
        self._closing_pages[page] = 0
        for pane in running:
            pane.feed_child_text(pane.provider.graceful_exit() or "")
        GLib.timeout_add(300, self._poll_graceful, page)

    def _poll_graceful(self, page: Adw.TabPage) -> bool:
        if page not in self._closing_pages:
            return GLib.SOURCE_REMOVE  # already closed
        panes = self._panes_of(page)
        if not any(pane.has_running_command() for pane in panes):
            for pane in panes:
                pane.feed_child_text("exit\r")  # a shell left over closes, and the tab with it
            return GLib.SOURCE_REMOVE
        self._closing_pages[page] += 1
        if self._closing_pages[page] >= 40:  # ~12s safety net
            self._close_confirmed(page)
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _sync_status(self, session_id: str) -> None:
        page = self._pages.get(session_id)
        if page is None:
            status = ""
        elif page.get_needs_attention():
            status = "attention"
        else:
            status = "open"
        self.store.set_status(session_id, status)
        self._queue_spaces_refresh()

    def _tab_of(self, page: Adw.TabPage) -> Gtk.Widget:
        """A page's own tab widget: for terminals, the primary pane."""
        child = page.get_child()
        return child.primary if isinstance(child, PaneContainer) else child

    def _session_id_of(self, page: Adw.TabPage) -> str | None:
        tab = self._tab_of(page)
        if isinstance(tab, TerminalTab):
            return self._pane_session(tab)
        return None

    @staticmethod
    def _pane_session(pane: TerminalTab) -> str | None:
        return pane.session_id if pane.session_id and not pane.fork else None

    def _panes_of(self, page: Adw.TabPage) -> list[TerminalTab]:
        child = page.get_child()
        return child.panes() if isinstance(child, PaneContainer) else []

    def _session_ids_of(self, page: Adw.TabPage) -> list[str]:
        return [sid for pane in self._panes_of(page) if (sid := self._pane_session(pane))]

    def _page_of(self, pane: TerminalTab) -> Adw.TabPage | None:
        container = pane.get_ancestor(PaneContainer)
        return self.tab_view.get_page(container) if isinstance(container, PaneContainer) else None

    def _watch_pane(self, pane: TerminalTab) -> None:
        pane.connect("process-exited", self._on_pane_exited)
        pane.connect("agent-state", self._on_pane_state)

    # -- agent states ----------------------------------------------------------

    def _on_pane_state(self, pane: TerminalTab, raw: str) -> None:
        """working / blocked / idle from the terminal; an agent that finished
        while you weren't looking is "done" until you view it (as in herdr)."""
        page = self._page_of(pane)
        if page is None:
            return
        previous = self._pane_state.get(pane, "idle")
        unseen = page is not self.tab_view.get_selected_page() or not self.is_active()
        state = raw
        if raw == "idle" and previous in ("working", "done") and unseen:
            state = "done"
        self._pane_state[pane] = state
        self._refresh_page_state(page)
        if unseen and state != previous and state in ("done", "blocked"):
            self._notify_state(page, state, pane)

    def _refresh_page_state(self, page: Adw.TabPage) -> None:
        self._set_page_state(page, rollup([self._pane_state.get(p, "idle") for p in self._panes_of(page)]))

    def _set_page_state(self, page: Adw.TabPage, state: str) -> None:
        changed = self._page_state.get(page) != state
        self._page_state[page] = state
        page.set_needs_attention(state in ("done", "blocked"))
        for session_id in self._session_ids_of(page):
            self._sync_status(session_id)
        if changed:
            self._queue_spaces_refresh()

    def _mark_seen(self, *_args) -> None:
        page = self.tab_view.get_selected_page()
        if page is None or not self.is_active():
            return
        for pane in self._panes_of(page):
            if self._pane_state.get(pane) == "done":
                self._pane_state[pane] = "idle"
        self._refresh_page_state(page)

    def _notify_state(self, page: Adw.TabPage, state: str, pane: TerminalTab | None = None) -> None:
        """Like herdr: a sound, plus a toast while you're in the window or a
        desktop notification while you're not."""
        if self.state.get_setting("notify_sound"):
            self._play_sound(state)
        app = self.get_application()
        if app is None or not self.state.get_setting("notify_idle"):
            return
        tab = pane or self._tab_of(page)
        agent = tab.provider.name if isinstance(tab, TerminalTab) else ""
        if state == "blocked":
            body = _("{agent} needs your input.").format(agent=agent)
        else:
            body = _("{agent} finished.").format(agent=agent)
        target = (self._pane_session(pane) if pane else self._session_id_of(page)) or page.get_title()
        if self.is_active():
            toast = Adw.Toast(title=f"{page.get_title()}: {body}", timeout=6)
            toast.set_button_label(_("Show"))
            toast.set_action_name("app.focus-session")
            toast.set_action_target_value(GLib.Variant("s", target))
            self.toasts.add_toast(toast)
            return
        notification = Gio.Notification.new(page.get_title())
        notification.set_body(body)
        notification.set_default_action(  # works on every PyGObject, unlike *_and_target_value
            Gio.Action.print_detailed_name("app.focus-session", GLib.Variant("s", target))
        )
        app.send_notification(target, notification)

    def _play_sound(self, state: str) -> None:
        name = "dialog-warning" if state == "blocked" else "complete"
        path = f"/usr/share/sounds/freedesktop/stereo/{name}.oga"
        if not Path(path).exists():  # no sound theme installed
            self.get_display().beep()
            return
        self._sound = Gtk.MediaFile.new_for_filename(path)  # keep a ref while it plays
        self._sound.play()

    def _on_selected_page_changed(self, view: Adw.TabView, _pspec) -> None:
        page = view.get_selected_page()
        self._queue_spaces_refresh()
        if page is None:
            return
        if self._page_space.get(page, (None,))[0] != self._project_id:
            self._show_project_tabs()  # the view moved to another project's tab: come back
            return
        if page in self._page_space:
            self._space_last[self._page_space[page][0]] = page
        self._mark_seen()
        child = page.get_child()
        if isinstance(child, PaneContainer):
            GLib.idle_add(child.focused.grab_terminal_focus)

    def focus_session(self, target: str) -> None:
        """Select the tab of a session id (or, for unsaved tabs, a title)."""
        page = self._pages.get(target) or next((t.page for t in self._tab_infos() if t.title == target), None)
        if page is not None:
            self.tab_view.set_selected_page(page)

    # -- spaces --------------------------------------------------------------

    def _tab_infos(self) -> list[TabInfo]:
        infos = []
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            space, agent = self._page_space.get(page, (str(Path.home()), ""))
            state = self._page_state.get(page, "idle")
            infos.append(
                TabInfo(
                    page,
                    page.get_title(),
                    space,
                    agent,
                    state,
                    self._tab_emoji(page),
                    self._tab_color(page),
                    self._tab_context(page),
                )
            )
        return infos

    def _tab_context(self, page: Adw.TabPage) -> ContextReading | None:
        """The fullest context among the tab's sessions: the one about to run out is what matters."""
        readings = [r for sid in self._session_ids_of(page) if (r := self.context.get(sid)) is not None]
        return max(readings, key=lambda reading: reading.percentage, default=None)

    def _on_context_changed(self, _model: ContextModel, session_id: str) -> None:
        self.project_list.set_reading(session_id, self.context.get(session_id))
        self._queue_spaces_refresh()

    def _tab_color(self, page: Adw.TabPage) -> str:
        """The group's color when every session in the tab is in that one group."""
        session_ids = self._session_ids_of(page)
        owner = self.state.projects.owner(session_ids[0]) if session_ids else None
        if owner is None:
            return ""
        groups = {g.name: g for g in owner.groups for sid in session_ids if sid in g.members}
        in_one = len(groups) == 1 and all(sid in next(iter(groups.values())).members for sid in session_ids)
        return next(iter(groups.values())).color if in_one else ""

    def _queue_spaces_refresh(self) -> None:
        if self._spaces_refresh_source is None:
            self._spaces_refresh_source = GLib.idle_add(self._refresh_spaces)
        self._queue_layout_save()

    # -- the saved layout, several windows ---------------------------------------------------

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def closing(self) -> bool:
        return self._closing_confirmed

    def _app(self) -> _Host | None:
        """The application, when it is the one that keeps the windows (not in a bare test window)."""
        app = self.get_application()
        return cast("_Host", app) if hasattr(app, "save_layout") else None

    def snapshot(self) -> WindowLayout:
        """This window's project and the sessions in its tabs, as they would reopen."""
        layout = WindowLayout(self._project_id)
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            session_ids = self._session_ids_of(page)
            if not session_ids or page not in self._page_space:
                continue
            child = page.get_child()
            split = child.get_first_child() if isinstance(child, PaneContainer) else None
            vertical = isinstance(split, Gtk.Paned) and split.get_orientation() == Gtk.Orientation.VERTICAL
            orientation = Orientation.VERTICAL if vertical else Orientation.HORIZONTAL
            layout.tabs.setdefault(self._page_space[page][0], []).append(TabLayout(session_ids, orientation))
        return layout

    def _queue_layout_save(self) -> None:
        if self._layout_save_source is None:
            self._layout_save_source = GLib.timeout_add(500, self._save_layout)

    def _save_layout(self) -> bool:
        self._layout_save_source = None
        app = self._app()
        if app is not None:
            app.save_layout()
        return GLib.SOURCE_REMOVE

    def restore_when_ready(self, layout: WindowLayout) -> None:
        """Reopen saved tabs once the store knows the sessions (its first scan is off the thread)."""
        if self.store.sessions:
            self._restore(layout)
            return
        handler: list[int] = []

        def once(*_args) -> None:
            self.store.disconnect(handler[0])
            self._restore(layout)

        handler.append(self.store.connect("refreshed", once))

    def _restore(self, layout: WindowLayout) -> None:
        shown = layout.current
        for project_id, tabs in layout.tabs.items():
            self._project_id = project_id  # a new tab belongs to the project this window shows
            for tab in tabs:
                first = self.store.get_session(tab.panes[0])
                if first is None:
                    continue
                self.open_session(first)
                for other in tab.panes[1:]:
                    self._open_beside(other)
                if tab.orientation == Orientation.VERTICAL and (panes := self._panes()) is not None:
                    panes.toggle_orientation()
        self._project_id = shown
        self._show_project_tabs()
        self._refresh_project()
        self._queue_spaces_refresh()

    def running_names(self) -> list[str]:
        names = []
        for i in range(self.tab_view.get_n_pages()):
            for pane in self._panes_of(self.tab_view.get_nth_page(i)):
                if pane.has_running_command():
                    session_id = self._pane_session(pane)
                    names.append(self._display(session_id) if session_id else pane.provider.name)
        return names

    def _on_close_request(self, _window) -> bool:
        if self._closing_confirmed:
            return False
        names = self.running_names()
        app = self._app()
        if not names:
            self._closing_confirmed = True
            if app is not None:
                app.window_closing(self)
            return False

        def confirm() -> None:
            self._closing_confirmed = True
            if app is not None:
                app.window_closing(self)  # the layout is kept before the tabs go
            for i in reversed(range(self.tab_view.get_n_pages())):
                self.tab_view.close_page(self.tab_view.get_nth_page(i))
            GLib.timeout_add(300, self._close_when_empty, [0])

        dialogs.confirm_dialog(
            self,
            _("Stop {n} running session(s)?").format(n=len(names)),
            ", ".join(names) + "\n\n" + _("Their conversations stay in Claude."),
            _("Stop and close"),
            confirm,
        )
        return True

    def _close_when_empty(self, polls: list[int]) -> bool:
        polls[0] += 1
        if self.tab_view.get_n_pages() == 0 or polls[0] > 50:  # ~15 s, past the force-close
            self.close()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _refresh_spaces(self) -> bool:
        self._spaces_refresh_source = None
        infos = self._tab_infos()
        selected = self.tab_view.get_selected_page()
        current = next((t for t in infos if t.page is selected), None)
        mine = [t for t in infos if t.space == self._project_id]
        self.tab_strip.update(mine, current if current in mine else None)
        states = self._session_states()
        self.project_list.set_states(states)
        self._update_project_bar(states)
        return GLib.SOURCE_REMOVE

    def _current_space(self) -> str | None:
        return self._project_id

    def _cycle_space_tab(self, step: int) -> None:
        space = self._current_space()
        pages = [t.page for t in self._tab_infos() if t.space == space]
        selected = self.tab_view.get_selected_page()
        if len(pages) > 1 and selected is not None and selected in pages:
            index = (pages.index(selected) + step) % len(pages)
            self.tab_view.set_selected_page(pages[index])

    def _on_tab_strip_menu(self, _strip, page: Adw.TabPage, widget: Gtk.Widget) -> None:
        self._menu_page = page
        popover = Gtk.PopoverMenu.new_from_model(self.tab_menu)
        popover.set_parent(widget)
        popover.set_has_arrow(False)

        def on_closed(p: Gtk.PopoverMenu) -> None:
            def release() -> bool:  # after the chosen action ran
                p.unparent()
                self._menu_page = None
                return GLib.SOURCE_REMOVE

            GLib.idle_add(release)

        popover.connect("closed", on_closed)
        popover.popup()

    # -- tab rename / menu ---------------------------------------------------

    def _rename_tab(self) -> None:
        page = self._menu_page or self.tab_view.get_selected_page()
        if page is None:
            return
        session_id = self._session_id_of(page)
        if session_id:  # real session tab → rename the session (syncs sidebar)
            session = self.store.get_session(session_id)
            if session is not None:
                self._prompt_rename_session(session)
            return
        # fork / new-session tab → local title rename only
        dialogs.rename_dialog(
            self,
            _("Tab name"),
            page.get_title(),
            lambda name: page.set_title(name.strip() or page.get_title()),
        )

    def _set_tab_emoji(self, page: Adw.TabPage | None = None) -> None:
        """Open the emoji picker at the tab; a pick applies at once."""
        page = page or self._menu_page or self.tab_view.get_selected_page()
        if page is None:
            return
        chooser = Gtk.EmojiChooser()
        if self._tab_emoji(page):
            _add_remove_button(chooser, lambda: self._apply_tab_emoji(page, ""))
        # Parent on the strip, not the tab button: the strip rebuilds its
        # buttons on every agent-state change, which would orphan the picker.
        chooser.set_parent(self.tab_strip)
        bounds = self.tab_strip.tab_bounds(page)
        if bounds is not None:
            chooser.set_pointing_to(bounds)
        chooser.connect("emoji-picked", lambda _c, text: self._apply_tab_emoji(page, text))
        chooser.connect("closed", lambda c: GLib.idle_add(c.unparent))
        chooser.popup()

    def _toggle_tab_emoji(self) -> None:
        """Ctrl+Shift+E: toggle a 😊 marker on the current tab — no menu."""
        page = self.tab_view.get_selected_page()
        if page is not None:
            self._apply_tab_emoji(page, "😊")

    def _remove_tab_emoji(self) -> None:
        page = self._menu_page or self.tab_view.get_selected_page()
        if page is not None:
            self._apply_tab_emoji(page, "")

    def _tab_emoji(self, page: Adw.TabPage) -> str:
        """The emoji a tab currently shows ('' if none)."""
        session_id = self._session_id_of(page)
        if session_id:
            return self.state.get_emoji(session_id) or ""
        base = self._base_titles.get(page)  # fork / new tab: a local title prefix
        title = page.get_title()
        if base is None or title == base or not title.endswith(base):
            return ""
        return title[: -len(base)].strip()

    def _apply_tab_emoji(self, page: Adw.TabPage, emoji: str) -> None:
        """Set a tab's one emoji (replacing any other); picking the one it
        already has removes it."""
        emoji = "" if emoji == self._tab_emoji(page) else emoji
        session_id = self._session_id_of(page)
        if session_id:
            self.state.set_emoji(session_id, emoji)
            session = self.store.get_session(session_id)
            if session is not None:
                page.set_title(self._tab_title(session))
            return
        base = self._base_titles.setdefault(page, page.get_title())
        page.set_title(f"{emoji} {base}" if emoji else base)

    def _copy_tab_session_id(self) -> None:
        page = self._menu_page or self.tab_view.get_selected_page()
        if page is None:
            return
        tab = self._tab_of(page)
        if isinstance(tab, TerminalTab) and tab.session_id:
            self.get_clipboard().set(tab.session_id)

    def _close_menu_tab(self) -> None:
        page = self._menu_page or self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    # -- panes & the Ctrl+B prefix ----------------------------------------------

    def _panes(self) -> PaneContainer | None:
        page = self.tab_view.get_selected_page()
        child = page.get_child() if page is not None else None
        return child if isinstance(child, PaneContainer) else None

    def _split(self, orientation: Gtk.Orientation) -> None:
        """A shell pane next to the focused one, in the tab's folder."""
        panes = self._panes()
        if panes is None:
            return
        if len(panes.panes()) >= MAX_PANES:
            self.toasts.add_toast(Adw.Toast(title=_("A tab holds two panes at most"), timeout=4))
            return
        primary = panes.primary
        pane = TerminalTab(
            cwd=primary.cwd, settings=self.state.settings, provider=primary.provider, shell=True
        )
        self._watch_pane(pane)
        panes.split(pane, orientation)

    def _close_pane(self) -> None:
        """Close the focused pane; on the agent's own pane, close the tab."""
        panes = self._panes()
        if panes is None:
            return
        pane = panes.focused
        if len(panes.panes()) == 1:
            self._close_current_tab()
            return
        self._stop_pane(pane)

    def _goto_tab(self, number: int) -> None:
        space = self._current_space()
        pages = [t.page for t in self._tab_infos() if t.space == space]
        if 0 < number <= len(pages):
            self.tab_view.set_selected_page(pages[number - 1])

    def _prefix_commands(self) -> list[tuple[list[int], str, str, Callable[[int], object]]]:
        """What follows Ctrl+B (herdr's defaults): (keyvals, keys as shown in
        the help, description, callback(keyval))."""

        def panes(method: str, *args) -> Callable[[int], object]:
            return lambda _kv: (p := self._panes()) is not None and getattr(p, method)(*args)

        def act(name: str) -> Callable[[int], object]:
            return lambda _kv: self.activate_action(f"win.{name}", None)

        k = Gdk
        return [
            (
                [k.KEY_v, k.KEY_percent],
                "v  %",
                _("split right (a shell)"),
                lambda _kv: self._split(Gtk.Orientation.HORIZONTAL),
            ),
            (
                [k.KEY_minus, k.KEY_quotedbl],
                '-  "',
                _("split down (a shell)"),
                lambda _kv: self._split(Gtk.Orientation.VERTICAL),
            ),
            ([k.KEY_h, k.KEY_Left], "h  ←", _("pane to the left"), panes("focus_direction", "left")),
            ([k.KEY_j, k.KEY_Down], "j  ↓", _("pane below"), panes("focus_direction", "down")),
            ([k.KEY_k, k.KEY_Up], "k  ↑", _("pane above"), panes("focus_direction", "up")),
            ([k.KEY_l, k.KEY_Right], "l  →", _("pane to the right"), panes("focus_direction", "right")),
            ([k.KEY_Tab], "Tab", _("next pane"), panes("cycle", 1)),
            ([k.KEY_z], "z", _("zoom the pane"), panes("toggle_zoom")),
            ([k.KEY_x], "x", _("close the pane"), lambda _kv: self._close_pane()),
            ([k.KEY_c], "c", _("new session in this project"), act("new-in-space")),
            ([k.KEY_n], "n", _("next tab"), act("next-tab")),
            ([k.KEY_p], "p", _("previous tab"), act("prev-tab")),
            (
                [getattr(k, f"KEY_{n}") for n in range(1, 10)],
                "1–9",
                _("go to tab"),
                lambda kv: self._goto_tab(kv - k.KEY_0),
            ),
            ([k.KEY_N], "N", _("add a session"), act("new-space")),
            ([k.KEY_T], "T", _("rename tab"), act("rename-tab")),
            ([k.KEY_X], "X", _("close tab"), act("close-tab")),
            ([k.KEY_g], "g", _("go to agent"), lambda _kv: self._goto_picker()),
            ([k.KEY_b], "b", _("toggle sidebar"), act("toggle-sidebar")),
            ([k.KEY_s], "s", _("preferences"), act("preferences")),
            ([k.KEY_question], "?", _("this help"), lambda _kv: self._show_prefix_help()),
        ]

    def _set_prefix(self, active: bool) -> None:
        self._prefix = active
        self.tab_strip.set_prefix(active)

    def _on_prefix_key(self, _ctrl, keyval: int, _keycode: int, state: Gdk.ModifierType) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if not self._prefix:
            focus = self.get_focus()
            typing = focus is not None and (
                isinstance(focus, Gtk.Text) or focus.get_ancestor(Adw.Dialog) is not None
            )  # a search field or a dialog keeps its own Ctrl+B
            if ctrl and keyval in (Gdk.KEY_b, Gdk.KEY_B) and not typing:
                self._set_prefix(True)
                return True
            return False
        if keyval in _MODIFIER_KEYS:
            return True  # e.g. Shift on the way to "N"
        self._set_prefix(False)
        if ctrl and keyval in (Gdk.KEY_b, Gdk.KEY_B):  # Ctrl+B twice: send it through
            if (panes := self._panes()) is not None:
                panes.focused.feed_child_text("\x02")
            return True
        for keyvals, _keys, _text, callback in self._prefix_commands():
            if keyval in keyvals:
                callback(keyval)
                break
        return True  # like tmux, an unknown key just ends the prefix

    def _show_prefix_help(self) -> None:
        rows = [(keys, text) for _kv, keys, text, _cb in self._prefix_commands()]
        rows.append(("Ctrl+B", _("send Ctrl+B to the terminal")))
        label = Gtk.Label(label="\n".join(f"{keys:<8} {text}" for keys, text in rows), xalign=0.0)
        label.add_css_class("monospace")
        dialog = Adw.AlertDialog(heading=_("Ctrl+B, then…"))
        dialog.set_extra_child(label)
        dialog.add_response("ok", _("OK"))
        dialog.present(self)

    def _on_pane_exited(self, pane: TerminalTab, _status: int) -> None:
        page = self._page_of(pane)
        if page is None:
            return
        panes = page.get_child()
        if not isinstance(panes, PaneContainer) or len(panes.panes()) == 1:
            self.tab_view.close_page(page)
            return
        panes.close(pane)
        self._pane_state.pop(pane, None)
        session_id = self._pane_session(pane)
        if session_id:
            self._pages.pop(session_id, None)
            self._sync_status(session_id)
        self._retitle(page)
        self._refresh_page_state(page)

    def _stop_pane(self, pane: TerminalTab) -> None:
        """Stop one pane of a split: an agent exits cleanly (its shell ends with it), a shell hangs up."""
        exit_text = pane.provider.graceful_exit() if self._pane_session(pane) else None
        if exit_text and pane.has_running_command():
            pane.feed_child_text(exit_text)
        else:
            pane.hangup()

    def _on_close_page(self, view: Adw.TabView, page: Adw.TabPage) -> bool:
        moving = page in self._moving
        running = any(pane.has_running_command() for pane in self._panes_of(page))
        if not moving and page not in self._confirmed_closes and running:
            if page not in self._closing_pages:  # start a graceful /exit in the background
                self._graceful_close(page)
            view.close_page_finish(page, False)  # keep the tab until it exits cleanly
            return True
        child = page.get_child()
        if isinstance(child, PaneContainer) and not moving:  # end the split shells with the tab
            for pane in child.panes():
                if pane is not child.primary:
                    pane.hangup()
                self._pane_state.pop(pane, None)
        self._moving.discard(page)
        for joining in self._joining:
            if joining.page is page:
                joining.closed = True  # a message typed just before closing still counts
        self._confirmed_closes.discard(page)
        self._closing_pages.pop(page, None)
        self._base_titles.pop(page, None)
        self._page_space.pop(page, None)
        self._page_state.pop(page, None)
        self._space_last = {k: v for k, v in self._space_last.items() if v is not page}
        for session_id, open_page in list(self._pages.items()):
            if open_page is page:
                self._pages.pop(session_id, None)
                self._sync_status(session_id)
        view.close_page_finish(page, True)
        if not any(space == self._project_id for space, _agent in self._page_space.values()):
            self.content_stack.set_visible_child_name("empty")
        return True  # we handled it

    # -- per-session actions ---------------------------------------------------

    def _session_for(self, param: GLib.Variant) -> Session | None:
        return self.store.get_session(param.get_string())

    def _on_open_action(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session:
            self.open_session(session)

    def _on_fork_action(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session:
            self.open_session(session, fork=True)

    def _on_open_ghostty(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None or _GHOSTTY is None:
            return
        provider = get_provider(session.provider)
        if shutil.which(provider.cli) is None:
            return
        cwd = session.cwd if session.cwd and Path(session.cwd).is_dir() else str(Path.home())
        subprocess.Popen(
            [_GHOSTTY, f"--working-directory={cwd}", "-e", provider.cli, "--resume", session.session_id],
            start_new_session=True,
        )

    def _on_rename_action(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is not None:
            self._prompt_rename_session(session)

    def _prompt_rename_session(self, session: Session) -> None:
        if session.claude_name:
            dialogs.error_dialog(
                self,
                _("This name comes from Claude"),
                _("Change it with /rename inside the session; the list follows on its next refresh."),
            )
            return

        def save(name: str) -> None:
            self.store.rename(session.session_id, name)
            page = self._pages.get(session.session_id)
            if page is not None:
                page.set_title(self._tab_title(session))

        dialogs.rename_dialog(
            self,
            session.preview or session.session_id,
            self.state.get_name(session.session_id) or "",
            save,
        )

    def _on_reveal_transcript(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(str(session.jsonl_path)))
        launcher.open_containing_folder(self, None, None)

    def _on_export_session(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return
        title = self.store.display_name(session)
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip() or "session"
        dialog = Gtk.FileDialog(title=_("Export session as Markdown"), initial_name=f"{safe}.md")
        dialog.save(self, None, lambda d, r: self._on_export_save(d, r, session, title))

    def _on_export_save(self, dialog: Gtk.FileDialog, result, session: Session, title: str) -> None:
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return  # cancelled
        dest = dialogs.require_local_path(gfile, self, _("Choose a local file"))
        if dest is None:
            return

        def work() -> None:
            error = None
            try:
                text = export_markdown(session.jsonl_path, title, session.session_id, session.cwd)
                Path(dest).write_text(text, encoding="utf-8")
            except OSError as err:
                error = str(err)
            if error:
                GLib.idle_add(dialogs.error_dialog, self, _("Export failed"), error)

        threading.Thread(target=work, daemon=True).start()

    def _on_session_details(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is not None:
            dialogs.details_dialog(self, session, self.store.display_name(session))

    def _on_hide_session(self, _action, param: GLib.Variant) -> None:
        session_id = param.get_string()
        self.store.set_hidden(session_id, not self.state.is_hidden(session_id))

    def _on_show_hidden(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self.store.set_show_hidden(value.get_boolean())

    def _on_trash_session(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return

        def do_trash() -> None:
            error = self.store.trash(session.session_id)
            if error:
                dialogs.error_dialog(self, _("Could not trash transcript"), error)
                return
            page = self._pages.get(session.session_id)
            if page is not None:
                self.tab_view.close_page(page)

        dialogs.confirm_dialog(
            self,
            _("Move transcript to trash?"),
            _("“{name}” will be removed from Claude's history.").format(name=self.store.display_name(session))
            + "\n"
            + _("The file is moved to the trash and can be restored."),
            _("Move to Trash"),
            do_trash,
        )

    def _on_delete_session(self, _action, param: GLib.Variant) -> None:
        session = self._session_for(param)
        if session is None:
            return

        def do_delete() -> None:
            error = self.store.delete(session.session_id)
            if error:
                dialogs.error_dialog(self, _("Could not delete transcript"), error)
                return
            page = self._pages.get(session.session_id)
            if page is not None:
                self.tab_view.close_page(page)

        dialogs.confirm_dialog(
            self,
            _("Delete session permanently?"),
            _("“{name}” and its transcript file will be permanently deleted. This cannot be undone.").format(
                name=self.store.display_name(session)
            ),
            _("Delete permanently"),
            do_delete,
        )

    # -- open transcript from file -----------------------------------------

    def _open_session_file(self) -> None:
        dialog = Gtk.FileDialog(title=_("Open session transcript"))
        jsonl_filter = Gtk.FileFilter()
        jsonl_filter.set_name(_("Session transcripts (*.jsonl)"))
        jsonl_filter.add_pattern("*.jsonl")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(jsonl_filter)
        dialog.set_filters(filters)
        dialog.set_default_filter(jsonl_filter)
        claude_dir = Path.home() / ".claude"
        if claude_dir.is_dir():
            dialog.set_initial_folder(Gio.File.new_for_path(str(claude_dir)))
        dialog.open(self, None, self._on_session_file_chosen)

    def _on_session_file_chosen(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return  # cancelled
        path = dialogs.require_local_path(gfile, self, _("Choose a local file"))
        if path is None:
            return
        session = session_from_file(Path(path))
        if session is None:
            dialogs.error_dialog(
                self,
                _("Could not open transcript"),
                _("The file couldn't be read as a session transcript."),
            )
            return
        self._open_replay(session)

    # -- preferences / about -------------------------------------------------

    def _show_usage(self) -> None:
        def memberships() -> dict[str, str]:
            return {sid: project.name for project in self.state.projects.projects for sid in project.members}

        def names() -> dict[str, str]:
            return {item.session_id: item.display_name for item in self.store.model_items()}

        UsageWindow(memberships, names, transient_for=self).present()

    def _show_about(self) -> None:
        about = Adw.AboutDialog(
            application_name="Agent Tablet",
            application_icon="io.github.hernancontigiani.AgentTablet",
            developer_name="Hernan Contigiani",
            version=__version__,
            license_type=Gtk.License.GPL_3_0,
            copyright="© 2026 Máté Molnár (Agent Session Manager)\n© 2026 Hernan Contigiani (Agent Tablet)",
            comments=(
                _(
                    "Manage and resume your AI coding agent sessions.\n\n"
                    "Unofficial community tool — not affiliated with or endorsed by Anthropic."
                )
            ),
            website="https://github.com/hernancontigiani/agent-tablet",
            issue_url="https://github.com/hernancontigiani/agent-tablet/issues",
        )
        about.add_credit_section(
            _("Based on"),
            ["Agent Session Manager by Máté Molnár https://github.com/r4nd3l/agent-session-manager"],
        )
        about.present(self)

    def _quick_switch(self) -> None:
        if self._switcher is not None:  # already open — don't stack another
            return
        entries = []
        members = set(self.state.projects.get(self._project_id).members)
        for item in self.store.model_items():
            if item.session_id not in members:
                continue
            subtitle = item.session.project_name
            if item.session.preview:
                subtitle += f" · {item.session.preview}"
            entries.append(SwitchEntry(item.display_name, subtitle, item, item.search_text))
        self._switcher = QuickSwitcher(
            entries,
            lambda item: self.open_session(item.session),
            _("Switch session"),
            _("Jump to a session…"),
        )
        self._switcher.connect("closed", self._on_switcher_closed)
        self._switcher.present(self)

    def _on_switcher_closed(self, *_args) -> None:
        self._switcher = None
        # the dialog hands focus back to its own entry; give it to the terminal
        panes = self._panes()
        if panes is not None:
            GLib.idle_add(panes.focused.grab_terminal_focus)

    def _goto_picker(self) -> None:
        """Prefix+g: jump to any running agent, grouped by space. Typing a
        state ("blocked", "working"…) filters by it, as herdr's b/w/i/d do."""
        if self._switcher is not None:
            return
        app = self._app()
        windows = app.windows() if app is not None else [self]
        entries = []
        for window in windows:
            infos = window._tab_infos()
            order = list(dict.fromkeys(t.space for t in infos))  # projects in tab order
            entries += [
                SwitchEntry(
                    f"{self._project_name(t.space)} · {t.title}",
                    f"{t.agent} · {t.status}",
                    (window, t),
                    f"{t.title} {self._project_name(t.space)} {t.agent} {t.status}",
                    t.status,
                )
                for t in sorted(infos, key=lambda t: order.index(t.space))
            ]

        def go(target: tuple[MainWindow, TabInfo]) -> None:
            window, info = target
            window.present()
            window._select_project(info.space)
            window.content_stack.set_visible_child_name("tabs")
            window.tab_view.set_selected_page(info.page)

        self._switcher = QuickSwitcher(entries, go, _("Go to agent"), _("Agent, project or state…"))
        self._switcher.connect("closed", self._on_switcher_closed)
        self._switcher.present(self)

    def _show_preferences(self) -> None:
        PreferencesDialog(self.state, self.apply_preferences).present(self)

    def apply_preferences(self) -> None:
        themes.apply_ui_style(self.state.settings)
        self._apply_settings_to_tabs()

    def _apply_settings_to_tabs(self) -> None:
        for i in range(self.tab_view.get_n_pages()):
            child = self.tab_view.get_nth_page(i).get_child()
            if isinstance(child, PaneContainer):
                for pane in child.panes():
                    pane.apply_settings(self.state.settings)
