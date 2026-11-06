import json
import os
import time
from pathlib import Path
from typing import Any, cast

import pytest

from tools.ui import locate, session

DECOY_HOME = "/home/someone-real"


def test_every_path_the_app_reads_is_under_the_session_dir(tmp_path):
    env = session.build_env(tmp_path, display=20, base_env={"HOME": DECOY_HOME, "PATH": "/usr/bin"})
    assert len(session.PATH_VARS) >= 8
    for key in session.PATH_VARS:
        assert env[key].startswith(str(tmp_path)), (key, env[key])
    assert all(value != DECOY_HOME for value in env.values())
    assert env["CSM_APP_ID"].endswith(".Dev")
    assert env["BROADWAY_DISPLAY"] == ":20"


def test_portals_are_disabled_for_the_isolated_app(tmp_path):
    env = session.build_env(tmp_path, display=20, base_env={})
    assert env["ADW_DISABLE_PORTAL"] == "1"
    assert env["GDK_DEBUG"] == "no-portals"


@pytest.mark.parametrize(
    ("sockets", "ports", "expected"),
    [
        pytest.param(set(), set(), 20, id="both-free"),
        pytest.param({20}, set(), 21, id="socket-taken"),
        pytest.param(set(), {8100}, 21, id="port-taken"),
        pytest.param({20, 21, 22}, {8103, 8104}, 25, id="both-taken-up-to-24"),
    ],
)
def test_allocation_skips_a_taken_display_and_a_taken_port(sockets, ports, expected):
    assert session.allocate(lambda n: n in sockets, lambda port: port in ports) == expected


def test_the_display_and_port_match_broadway_conventions():
    assert session.port_of(20) == 8100
    assert session.socket_name(20) == "broadway21.socket"


@pytest.mark.parametrize(("theme", "expected"), [(None, "dark"), ("light", "light")])
def test_the_isolated_state_asks_for_the_requested_theme(tmp_path, theme, expected):
    state_file = tmp_path / "config" / "agent-tablet" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"names": {"sid": "Kept"}, "settings": {}}), encoding="utf-8")

    if theme is None:
        session.write_isolated_state(tmp_path / "config")
    else:
        session.write_isolated_state(tmp_path / "config", theme=theme)

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["settings"]["color_scheme"] == expected
    assert data["names"] == {"sid": "Kept"}  # the demo's own state survives


def test_teardown_leaves_no_child_running(tmp_path):
    group = session.ProcessGroup()
    first = group.spawn(["sleep", "60"], env=dict(os.environ), log=tmp_path / "a.log")
    second = group.spawn(["sh", "-c", "sleep 60 & wait"], env=dict(os.environ), log=tmp_path / "b.log")
    pids = [first.pid, second.pid]
    assert all(_alive(pid) for pid in pids)

    group.close()

    deadline = time.monotonic() + 5
    while any(_alive(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not any(_alive(pid) for pid in pids)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    with open(f"/proc/{pid}/stat") as stat:  # a zombie is dead for this purpose
        return stat.read().split()[2] != "Z"


@pytest.fixture(scope="module")
def ui_tree():
    path = Path(__file__).parent / "data" / "ui_tree.json"
    tree = json.loads(path.read_text(encoding="utf-8"))
    assert sum(len(window["widgets"]) for window in tree) >= 100  # a dump, not a stub
    return tree


def test_find_by_type_returns_the_search_entry(ui_tree):
    window, widget = locate.find(ui_tree, type="SearchEntry")
    assert window["title"] == "Agent Tablet"
    assert widget["placeholder_text"] == "Search sessions…"


def test_find_by_text_reaches_a_project_row(ui_tree):
    _window, widget = locate.find(ui_tree, type="Label", text="TODO-API")
    assert widget["box"][2] > 0


def test_an_ambiguous_match_names_every_candidate(ui_tree):
    candidates = locate.find_all(ui_tree, css="count-badge")  # one per history group
    assert len(candidates) >= 5
    with pytest.raises(LookupError) as raised:
        locate.find(ui_tree, css="count-badge")
    assert str(raised.value).count("Label [") == len(candidates)


def test_no_match_says_what_was_asked(ui_tree):
    with pytest.raises(LookupError, match="no widget matches"):
        locate.find(ui_tree, text="Nothing like this")


def test_the_click_point_is_the_box_centre_offset_by_the_window():
    assert locate.click_point((61, 55), [8, 127, 340, 34]) == (239, 199)


SURFACES = [  # as Broadway's page reported them with the main menu open
    {"x": 0, "y": 0, "width": 1146, "height": 890, "offset": [61, 55]},
    {"x": 347, "y": 95, "width": 239, "height": 232, "offset": [0, 0]},
]


def test_the_window_origin_is_its_surface_plus_the_shadow_offset(ui_tree):
    window = ui_tree[0]
    main = window["natives"][window["widgets"][0]["native"]]
    assert main["surface_offset"] == [61, 55] and main["size"][0] == 1024
    assert locate.native_origin(main, SURFACES) == (61, 55)


def test_a_popover_item_is_placed_on_the_popover_surface_not_the_window():
    popover = {"type": "PopoverMenu", "size": [239, 232], "surface_offset": [0, 0]}
    window = {"natives": {"n1": popover}}
    item = {"native": "n1", "box": [64, 136, 75, 32]}  # "Preferences", relative to the popover
    assert locate.page_point(window, item, SURFACES) == (347 + 64 + 37.5, 95 + 136 + 16)


def test_a_socket_file_nobody_listens_on_does_not_take_a_display(tmp_path, monkeypatch):
    import socket as sockets

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    stale = sockets.socket(sockets.AF_UNIX)
    stale.bind(str(tmp_path / session.socket_name(20)))
    stale.close()  # the file stays, as after gtk4-broadwayd is killed
    live = sockets.socket(sockets.AF_UNIX)
    live.bind(str(tmp_path / session.socket_name(21)))
    live.listen()
    try:
        assert (tmp_path / session.socket_name(20)).exists()
        assert not session.socket_taken(20)
        assert session.socket_taken(21)
    finally:
        live.close()


def test_a_browser_that_fails_to_close_does_not_orphan_the_app(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "allocate", lambda *_a: 20)
    ui = session.UiSession(tmp_path, browser=False)
    child = ui._procs.spawn(["sleep", "60"], env=dict(os.environ), log=tmp_path / "app.log")

    class DeadBrowser:
        def close(self):
            raise RuntimeError("write EINVAL")

    ui._browser = cast(Any, DeadBrowser())  # a stand-in for Playwright's Browser
    with pytest.raises(RuntimeError):
        ui.close()
    deadline = time.monotonic() + 5
    while _alive(child.pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(child.pid)


def test_the_isolated_app_runs_the_fake_agent_first(tmp_path):
    """A tab opened by the walk runs a stand-in: a real agent with an empty HOME would start its
    login and reach the network."""
    env = session.build_env(tmp_path, display=20, base_env={"PATH": "/usr/bin:/bin"})
    session.write_fake_agent(tmp_path / "bin")
    assert env["PATH"].split(":") == [str(tmp_path / "bin"), "/usr/bin", "/bin"]
    assert (tmp_path / "bin" / "claude").stat().st_mode & 0o111


def test_the_isolated_app_never_inherits_claude_codes_markers(tmp_path):
    """A `claude` started with these saves no transcript; a walk is often run from Claude Code."""
    base = {
        "PATH": "/usr/bin",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_CHILD_SESSION": "1",
        "CLAUDE_PID": "7",
        "KEEP": "x",
    }
    env = session.build_env(tmp_path, display=20, base_env=base)
    assert not [k for k in env if k == "CLAUDECODE" or k.startswith("CLAUDE_")]
    assert env["KEEP"] == "x"


def test_with_the_real_agent_only_the_apps_own_state_is_isolated(tmp_path):
    env = session.build_env(
        tmp_path, display=20, base_env={"HOME": "/home/someone", "PATH": "/usr/bin"}, real_agent=True
    )
    assert env["HOME"] == "/home/someone"
    assert env["CSM_PROJECTS_DIR"] == "/home/someone/.claude/projects"
    for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        assert env[key].startswith(str(tmp_path)), key
    assert env["PATH"] == "/usr/bin"  # the user's own claude, not the stand-in
