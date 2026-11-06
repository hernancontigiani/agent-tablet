"""Which sessions are in which tab, which projects in which window, and how that is saved.

A session runs while it is in a tab, so it is in at most one tab across every window; a project is
in at most one window, so a session can never be open twice.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

MAX_PANES = 2


class Orientation(str, Enum):
    HORIZONTAL = "horizontal"  # side by side
    VERTICAL = "vertical"  # stacked


@dataclass
class TabLayout:
    panes: list[str]  # session ids; a shell pane is not saved
    orientation: Orientation = Orientation.HORIZONTAL


@dataclass
class WindowLayout:
    current: str  # the project the window shows
    tabs: dict[str, list[TabLayout]] = field(default_factory=dict)  # project id -> its tabs here

    @property
    def projects(self) -> set[str]:
        return {self.current, *self.tabs}


Where = tuple[Hashable, str, int]  # (window key, project id, tab index)


class Layouts:
    def __init__(self) -> None:
        self.windows: dict[Hashable, WindowLayout] = {}

    # -- windows -------------------------------------------------------------------------

    def add_window(self, key: Hashable, project_id: str, layout: WindowLayout | None = None) -> None:
        self.windows[key] = layout or WindowLayout(project_id)

    def remove_window(self, key: Hashable) -> None:
        self.windows.pop(key, None)

    def window_of(self, project_id: str) -> Hashable | None:
        return next((key for key, w in self.windows.items() if project_id in w.projects), None)

    def show(self, key: Hashable, project_id: str) -> Hashable | None:
        """Show a project in a window; if another window holds it, nothing changes and that window
        is returned."""
        holder = self.window_of(project_id)
        if holder is not None and holder != key:
            return holder
        self.windows[key].current = project_id
        return None

    def release(self, project_id: str) -> None:
        """A deleted project leaves every window; one that showed it shows another it holds."""
        for window in self.windows.values():
            window.tabs.pop(project_id, None)
            if window.current == project_id and window.tabs:
                window.current = next(iter(window.tabs))

    # -- tabs ----------------------------------------------------------------------------

    def tab_of(self, session_id: str) -> Where | None:
        for key, window in self.windows.items():
            for project_id, tabs in window.tabs.items():
                for index, tab in enumerate(tabs):
                    if session_id in tab.panes:
                        return key, project_id, index
        return None

    def open(self, key: Hashable, project_id: str, session_id: str) -> Where:
        """The session's tab, wherever it is; a new tab in this window if it has none."""
        where = self.tab_of(session_id)
        if where is not None:
            return where
        tabs = self.windows[key].tabs.setdefault(project_id, [])
        tabs.append(TabLayout([session_id]))
        return key, project_id, len(tabs) - 1

    def open_beside(self, key: Hashable, project_id: str, index: int, session_id: str) -> bool:
        tab = self.windows[key].tabs[project_id][index]
        if session_id in tab.panes or len(tab.panes) >= MAX_PANES:
            return False
        self.close_pane(session_id)
        tab.panes.append(session_id)
        return True

    def set_orientation(self, key: Hashable, project_id: str, index: int, orientation: Orientation) -> None:
        self.windows[key].tabs[project_id][index].orientation = orientation

    def close_pane(self, session_id: str) -> None:
        for window in self.windows.values():
            for project_id, tabs in window.tabs.items():
                for tab in tabs:
                    if session_id in tab.panes:
                        tab.panes.remove(session_id)
                window.tabs[project_id] = [t for t in tabs if t.panes]

    def close_tab(self, key: Hashable, project_id: str, index: int) -> list[str]:
        """Remove a tab; returns its sessions, which stop with it."""
        return self.windows[key].tabs[project_id].pop(index).panes

    def move_session(self, session_id: str, key: Hashable, project_id: str) -> None:
        """A session moved to another project takes its tab with it, alone."""
        if self.tab_of(session_id) is None:
            return
        self.close_pane(session_id)
        self.windows[key].tabs.setdefault(project_id, []).append(TabLayout([session_id]))

    # -- saving --------------------------------------------------------------------------

    def to_list(self) -> list[dict[str, Any]]:
        return [
            {
                "current": w.current,
                "tabs": {
                    project_id: [{"panes": list(t.panes), "orientation": t.orientation.value} for t in tabs]
                    for project_id, tabs in w.tabs.items()
                    if tabs
                },
            }
            for w in self.windows.values()
        ]


def new_window_project(project_ids: list[str], layouts: Layouts) -> str | None:
    return next((p for p in project_ids if layouts.window_of(p) is None), None)


def _tab_from(raw: Any, members: set[str], placed: set[str]) -> TabLayout | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("panes"), list):
        return None
    panes = [s for s in raw["panes"] if isinstance(s, str) and s in members and s not in placed][:MAX_PANES]
    if not panes:
        return None
    placed.update(panes)
    try:
        orientation = Orientation(raw.get("orientation", Orientation.HORIZONTAL.value))
    except ValueError:
        orientation = Orientation.HORIZONTAL
    return TabLayout(panes, orientation)


def restore(saved: Any, members: dict[str, set[str]], current: str, reopen_tabs: bool) -> list[WindowLayout]:
    """The windows to open on start. With reopen_tabs off, or nothing usable saved, one window on
    the current project with no tabs. Sessions no longer in their project are dropped."""
    fallback = [WindowLayout(current)]
    if not reopen_tabs or not isinstance(saved, list):
        return fallback
    windows: list[WindowLayout] = []
    taken: set[str] = set()
    placed: set[str] = set()
    for raw in saved:
        if not isinstance(raw, dict) or not isinstance(raw.get("current"), str):
            continue
        tabs_raw = raw.get("tabs")
        if not isinstance(tabs_raw, dict):
            tabs_raw = {}
        tabs: dict[str, list[TabLayout]] = {}
        for project_id, raw_tabs in tabs_raw.items():
            if project_id not in members or project_id in taken or not isinstance(raw_tabs, list):
                continue
            restored = [t for t in (_tab_from(r, members[project_id], placed) for r in raw_tabs) if t]
            if restored:
                tabs[project_id] = restored
        shown = raw["current"]
        if shown not in members or shown in taken:
            shown = next(iter(tabs), None)
        if shown is None:
            continue
        window = WindowLayout(shown, tabs)
        taken.update(window.projects)
        windows.append(window)
    return windows or fallback
