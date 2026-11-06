"""The Usage window: execution time, blocked time, tokens and cost, project → category → session,
for today, 7 days or 30 days. The numbers are `usage.report`'s, the same as `agent-tablet usage`."""

from __future__ import annotations

import threading
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

from . import clock, sessions, usage
from .i18n import _

_PERIODS = (("today", _("Today")), ("7d", _("7 days")), ("30d", _("30 days")))


def _tokens(count: int) -> str:
    return f"{count / 1_000_000:.1f}M" if count >= 1_000_000 else f"{count / 1000:.0f}k"


def _cost(node: usage.Node) -> str:
    text = ("$" if node.cost_exact else "~$") + f"{node.cost:.2f}"
    return text if node.all_priced else text + "+"


def _number(text: str, width: int) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=1.0, width_chars=width)
    label.add_css_class("numeric")
    return label


class UsageWindow(Adw.Window):
    """`memberships` and `names` are read when a report is built: a session's project and the name
    the app shows for it."""

    def __init__(
        self,
        memberships: Callable[[], dict[str, str]],
        names: Callable[[], dict[str, str]],
        **kwargs,
    ) -> None:
        super().__init__(title=_("Usage"), default_width=720, default_height=560, **kwargs)
        self._memberships = memberships
        self._names = names
        self._period = "7d"
        self._collapsed: set[tuple[str, ...]] = set()
        self._report: usage.Report | None = None

        header = Adw.HeaderBar()
        switcher = Gtk.Box(css_classes=["linked"])
        first: Gtk.ToggleButton | None = None
        for key, label in _PERIODS:
            button = Gtk.ToggleButton(label=label, active=key == self._period)
            if first is None:
                first = button
            else:
                button.set_group(first)
            button.connect("toggled", self._on_period, key)
            switcher.append(button)
        header.set_title_widget(switcher)

        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        self._footer = Gtk.Label(xalign=0.0, wrap=True)
        self._footer.add_css_class("dim-label")
        self._status = Adw.StatusPage(
            title=_("Reading the transcripts…"), icon_name="content-loading-symbolic"
        )

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12)
        body.set_margin_start(12)
        body.set_margin_end(12)
        body.append(self._heading())
        body.append(self._list)
        body.append(self._footer)
        scrolled = Gtk.ScrolledWindow(child=body, vexpand=True)
        self._stack = Gtk.Stack()
        self._stack.add_named(self._status, "loading")
        self._stack.add_named(scrolled, "report")

        toolbar = Adw.ToolbarView(content=self._stack)
        toolbar.add_top_bar(header)
        self.set_content(toolbar)
        self.refresh()

    @staticmethod
    def _heading() -> Gtk.Widget:
        row = Gtk.Box(spacing=12, margin_start=12, margin_end=12)
        name = Gtk.Label(label=_("Project / category / session"), xalign=0.0, hexpand=True)
        row.append(name)
        for text, width in ((_("Exec"), 7), (_("Blocked"), 8), (_("Tokens"), 8), (_("Cost"), 9)):
            row.append(_number(text, width))
        name.add_css_class("dim-label")
        return row

    def _on_period(self, button: Gtk.ToggleButton, key: str) -> None:
        if button.get_active() and key != self._period:
            self._period = key
            self.refresh()

    def refresh(self) -> None:
        """Read what the transcripts gained off the main thread, then show the report."""
        if self._report is None:
            self._stack.set_visible_child_name("loading")
        period = self._period
        memberships, names = self._memberships(), self._names()

        def work() -> None:
            cache = usage.UsageCache()  # a connection of its own: SQLite objects stay in one thread
            cache.ingest(sessions.CLAUDE_PROJECTS_DIR)
            start, end = usage.period_bounds(period, clock.now())
            result = usage.report(cache, start, end, memberships, usage.usage_log_path(), names)
            GLib.idle_add(self._show, period, result)

        threading.Thread(target=work, daemon=True).start()

    def _show(self, period: str, result: usage.Report) -> bool:
        if period != self._period:
            return GLib.SOURCE_REMOVE  # the user picked another period meanwhile
        self._report = result
        self._rebuild()
        self._stack.set_visible_child_name("report")
        return GLib.SOURCE_REMOVE

    def _rebuild(self) -> None:
        self._list.remove_all()
        report = self._report
        if report is None:
            return
        if not report.nodes:
            self._list.append(Gtk.Label(label=_("Nothing in this period."), margin_top=12, margin_bottom=12))
        for node in report.nodes:
            self._add(node, (node.label,), 0)
        blocked = sum(node.blocked for node in report.nodes)
        footer = _("Blocked waiting on you: {time}").format(time=usage.duration(blocked))
        if report.limits:
            footer += "   " + _("5-hour limit {five}% · 7-day {seven}%").format(
                five=f"{report.limits[0]:.0f}", seven=f"{report.limits[1]:.0f}"
            )
        footer += "\n" + _("~ is a list-price estimate, not a bill; + means a model with no price.")
        self._footer.set_label(footer)

    def _add(self, node: usage.Node, path: tuple[str, ...], depth: int) -> None:
        row = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6, margin_start=12 + 18 * depth, margin_end=12)
        if node.children:
            open_ = path not in self._collapsed
            toggle = Gtk.Button(icon_name="pan-down-symbolic" if open_ else "pan-end-symbolic")
            toggle.add_css_class("flat")
            toggle.connect("clicked", lambda *_: self._toggle(path))
            row.append(toggle)
        name = Gtk.Label(label=node.label, xalign=0.0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        if node.kind == "project":
            name.add_css_class("heading")
        row.append(name)
        execution = _number(usage.duration(node.total_execution), 7)
        if node.execution:
            parts = [
                f"{origin} {usage.duration(seconds)}" for origin, seconds in sorted(node.execution.items())
            ]
            execution.set_tooltip_text(_("Started by: {parts}").format(parts=", ".join(parts)))
        row.append(execution)
        row.append(_number(usage.duration(node.blocked), 8))
        row.append(_number(_tokens(node.tokens.total), 8))
        row.append(_number(_cost(node), 9))
        self._list.append(row)
        if node.children and path not in self._collapsed:
            for child in node.children:
                self._add(child, (*path, child.label), depth + 1)

    def _toggle(self, path: tuple[str, ...]) -> None:
        self._collapsed ^= {path}
        self._rebuild()
