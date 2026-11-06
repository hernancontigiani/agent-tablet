"""Application entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from . import dialogs, themes
from .context import ContextModel
from .i18n import _
from .layout import Layouts, new_window_project, restore
from .prefs import apply_color_scheme
from .projects import ProjectError
from .state import AppState
from .store import SessionStore
from .window import MainWindow

# Bundled icons (e.g. tab-close-symbolic); found by name when installed.
_BUNDLED_ICONS = Path(__file__).resolve().parent.parent / "data" / "icons"

_CSS = b"""
/* classic style: the terminal frame is invisible (TUI style draws it) */
frame.term-frame { border: none; border-radius: 0; }

.status-dot {
  min-width: 8px;
  min-height: 8px;
  border-radius: 100%;
  background-color: alpha(currentColor, 0.25);
}
.status-dot.open { background-color: #2ec27e; }
.status-dot.attention { background-color: #3584e4; }
/* agent states on open tabs (spaces / agents / tab strip) */
.status-dot.idle { background-color: transparent; box-shadow: inset 0 0 0 1.5px #2ec27e; }
.status-dot.working { background-color: #e5a50a; }
.status-dot.blocked { background-color: #e01b24; }
.status-dot.done { background-color: #2ec27e; }

.group-header { padding: 10px 10px 4px 10px; }

/* session-row state badges */
.waiting-badge { color: #e5a50a; }      /* Claude asked a question */
.interrupted-badge { color: #e01b24; }  /* user stopped Claude mid-task */

.status-dot.stopped {
  background-color: transparent;
  box-shadow: inset 0 0 0 1.5px alpha(currentColor, 0.35);
}
.blocked-badge {
  background-color: #e01b24;
  color: white;
  border-radius: 9px;
  padding: 0 6px;
  font-size: smaller;
  font-weight: bold;
}
.project-bar > button { padding: 4px 8px; }

.prefix-pill {
  background-color: @accent_bg_color;
  color: @accent_fg_color;
  font-weight: bold;
  font-size: 0.8em;
  padding: 1px 8px;
  margin: 0 6px;
}

/* per-space tab strip; the active tab clearly stands out */
.tab-strip { padding: 3px 6px; }
button.strip-tab { padding: 2px 10px; }
button.strip-tab:not(.selected) label { opacity: 0.6; }
button.strip-tab.selected {
  background-color: alpha(#D97757, 0.22);
  box-shadow: inset 0 -3px 0 #D97757;
}
button.strip-tab.selected label { font-weight: bold; }

.count-badge {
  background-color: alpha(currentColor, 0.1);
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 0.8em;
}

/* children connect to their group via a left guide line, on a faint card */
row.session-child {
  margin-left: 20px;
  margin-right: 16px;
  background-color: alpha(currentColor, 0.06);
  border-left: 2px solid alpha(currentColor, 0.15);
  border-radius: 0 8px 8px 0;
}
row.session-child:hover {
  background-color: alpha(currentColor, 0.1);
  border-left-color: alpha(currentColor, 0.3);
}

/* interactive prompt card overlaid on the terminal */
.chat-card {
  background-color: @window_bg_color;
  border: 1px solid alpha(#D97757, 0.6);
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 2px 12px alpha(black, 0.35);
}
.chat-card-header {
  color: #D97757;
  font-weight: bold;
  font-size: 0.85em;
}
.chat-option {
  padding: 8px 12px;
}
.chat-option-static {
  padding: 4px 8px;
}

/* chat-session tab: streaming bubbles + tool chips */
.chat-bubble {
  padding: 8px 12px;
  border-radius: 14px;
}
.chat-user {
  background-color: #D97757;
  color: white;
}
.chat-assistant {
  background-color: alpha(currentColor, 0.08);
}
.chat-tool {
  font-size: 0.85em;
  opacity: 0.6;
  padding: 2px 4px;
}
"""


APP_ID = "io.github.hernancontigiani.AgentTablet"


class App(Adw.Application):
    def __init__(self) -> None:
        # CSM_APP_ID lets a demo instance run alongside the real one (for screenshots).
        super().__init__(application_id=os.environ.get("CSM_APP_ID") or APP_ID)
        self._quitting = False  # the last window is closing: its tabs going must not erase the layout

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        display = Gdk.Display.get_default()
        assert display is not None  # a GTK app has started a display before do_startup
        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        if _BUNDLED_ICONS.is_dir():  # running from source; installed icons live in the system theme
            Gtk.IconTheme.get_for_display(display).add_search_path(str(_BUNDLED_ICONS))

        # Shared across all windows so scans/monitors aren't duplicated and
        # state.json writes don't race.
        self.state = AppState()
        apply_color_scheme(self.state.get_setting("color_scheme"))
        themes.apply_ui_style(self.state.settings)
        # "Default" theme follows light/dark, so recolor when the scheme flips
        Adw.StyleManager.get_default().connect("notify::dark", self._on_dark_changed)
        self.store = SessionStore(self.state)
        self.store.start()
        self.context = ContextModel()

        focus = Gio.SimpleAction.new("focus-session", GLib.VariantType("s"))
        focus.connect("activate", self._on_focus_session)
        self.add_action(focus)

        new_window = Gio.SimpleAction.new("new-window", None)
        new_window.connect("activate", lambda *_: self._open_new_window())
        self.add_action(new_window)
        self.set_accels_for_action("app.new-window", ["<Control><Shift>n"])

    def _on_dark_changed(self, *_args) -> None:
        themes.apply_ui_style(self.state.settings)
        for window in self.get_windows():
            if isinstance(window, MainWindow):
                window.apply_preferences()

    def _new_window(self, project_id: str | None = None) -> MainWindow:
        window = MainWindow(
            application=self, state=self.state, store=self.store, project_id=project_id, context=self.context
        )
        window.present()
        return window

    # -- the windows and what each one holds -----------------------------------------------

    def windows(self) -> list[MainWindow]:
        return [w for w in self.get_windows() if isinstance(w, MainWindow)]

    def layouts(self, but: MainWindow | None = None) -> Layouts:
        layouts = Layouts()
        for window in self.windows():
            if window is not but and not window.closing:
                layouts.add_window(window, window.project_id, window.snapshot())
        return layouts

    def window_holding(self, project_id: str, but: MainWindow | None = None) -> MainWindow | None:
        holder = self.layouts(but=but).window_of(project_id)
        return holder if isinstance(holder, MainWindow) else None

    def held_elsewhere(self, window: MainWindow) -> set[str]:
        return {pid for w in self.layouts(but=window).windows.values() for pid in w.projects}

    def all_states(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for window in self.windows():
            states.update(window._session_states())
        return states

    def save_layout(self) -> None:
        if self._quitting:
            return
        self.state.projects.windows = self.layouts().to_list()
        self.state.save_projects()

    def window_closing(self, window: MainWindow) -> None:
        """A window closing on its own leaves the saved layout; the last one keeps it whole."""
        others = [w for w in self.windows() if w is not window and not w.closing]
        layouts = self.layouts(but=window) if others else Layouts()
        if not others:
            layouts.add_window(window, window.project_id, window.snapshot())
        self.state.projects.windows = layouts.to_list()
        self.state.save_projects()
        if not others:
            self._quitting = True

    def _open_new_window(self) -> None:
        project_id = new_window_project([p.id for p in self.state.projects.projects], self.layouts())
        if project_id is not None:
            self._new_window(project_id)
            return
        parent = self.get_active_window()

        def create(name: str) -> None:
            try:
                project = self.state.projects.create(name)
            except ProjectError as error:
                dialogs.error_dialog(parent, _("No new window"), str(error))
                return
            self.state.save_projects()
            self._new_window(project.id)

        if parent is not None:
            dialogs.text_dialog(
                parent,
                _("New project"),
                _("Every project is open in a window already; a new window needs a new project."),
                "",
                _("Name"),
                create,
            )

    def _on_focus_session(self, _action, param: GLib.Variant) -> None:
        session_id = param.get_string()
        window = next((w for w in self.windows() if session_id in w._pages), None) or self.get_active_window()
        if window is None:
            return
        window.present()
        if session_id and isinstance(window, MainWindow):
            window.focus_session(session_id)

    def do_activate(self) -> None:
        window = self.get_active_window()
        if window is not None:
            window.present()
            return
        projects = self.state.projects
        members = {p.id: set(p.members) for p in projects.projects}
        reopen = bool(self.state.get_setting("reopen_tabs"))
        for layout in restore(projects.windows, members, projects.current, reopen):
            self._new_window(layout.current).restore_when_ready(layout)


def main() -> int:
    from . import i18n, log
    from .state import AppState

    if sys.argv[1:2] == ["usage"]:  # `agent-tablet usage`: the report in the terminal, no window
        from . import usage

        return usage.main(sys.argv[2:])
    log.configure(os.environ)
    i18n.init(AppState().get_setting("language"))
    app = App()
    return app.run(sys.argv)
