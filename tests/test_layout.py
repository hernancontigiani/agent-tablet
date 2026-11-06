"""Tabs and windows as data: two panes at most, one tab per session, one window per project."""

import pytest

from agent_tablet.layout import Layouts, Orientation, TabLayout, WindowLayout, new_window_project, restore


@pytest.fixture
def layouts() -> Layouts:
    layouts = Layouts()
    layouts.add_window(1, "A")
    return layouts


def test_a_tab_layout_refuses_a_third_pane(layouts):
    layouts.open(1, "A", "s1")
    assert layouts.open_beside(1, "A", 0, "s2")
    assert not layouts.open_beside(1, "A", 0, "s3")
    assert layouts.windows[1].tabs["A"] == [TabLayout(["s1", "s2"])]
    assert layouts.tab_of("s3") is None


def test_a_session_already_in_a_tab_is_not_placed_in_another(layouts):
    assert layouts.open(1, "A", "s1") == (1, "A", 0)
    layouts.open(1, "A", "s2")
    assert layouts.open(1, "A", "s1") == (1, "A", 0)
    assert len(layouts.windows[1].tabs["A"]) == 2


def test_opening_beside_moves_a_session_out_of_its_own_tab(layouts):
    layouts.open(1, "A", "s1")
    layouts.open(1, "A", "s2")
    assert layouts.open_beside(1, "A", 0, "s2")
    assert layouts.windows[1].tabs["A"] == [TabLayout(["s1", "s2"])]


def test_closing_a_pane_keeps_the_other_and_an_empty_tab_goes(layouts):
    layouts.open(1, "A", "s1")
    layouts.open_beside(1, "A", 0, "s2")
    layouts.close_pane("s1")
    assert layouts.windows[1].tabs["A"] == [TabLayout(["s2"])]
    layouts.close_pane("s2")
    assert layouts.windows[1].tabs["A"] == []


def test_a_project_is_open_in_at_most_one_window(layouts):
    layouts.add_window(2, "B")
    assert layouts.show(2, "A") == 1  # told where it is; window 2 keeps showing B
    assert layouts.windows[2].current == "B"
    assert layouts.show(2, "C") is None
    assert layouts.windows[2].current == "C"
    assert layouts.window_of("B") is None  # shown before, no tab of it here: free for another window


def test_a_window_keeps_the_projects_it_showed_until_it_closes(layouts):
    layouts.open(1, "A", "s1")
    layouts.show(1, "B")
    assert layouts.window_of("A") == 1
    assert layouts.tab_of("s1") == (1, "A", 0)
    layouts.remove_window(1)
    assert layouts.window_of("A") is None
    assert layouts.tab_of("s1") is None


def test_moving_a_tab_to_another_window(layouts):
    layouts.add_window(2, "B")
    layouts.open(1, "A", "s1")
    layouts.move_session("s1", 2, "B")
    assert layouts.tab_of("s1") == (2, "B", 0)
    assert layouts.windows[1].tabs["A"] == []


@pytest.mark.parametrize(
    ("taken", "expected"),
    [
        pytest.param({"A"}, "B", id="a-free-project"),
        pytest.param({"A", "B"}, None, id="all-taken"),
    ],
)
def test_a_new_window_takes_a_project_in_no_window(taken, expected):
    layouts = Layouts()
    for key, project in enumerate(sorted(taken)):
        layouts.add_window(key, project)
    assert new_window_project(["A", "B"], layouts) == expected


SAVED = [
    {
        "current": "A",
        "tabs": {"A": [{"panes": ["s1", "s2"], "orientation": "vertical"}], "B": [{"panes": ["s3"]}]},
    },
    {"current": "C", "tabs": {"C": [{"panes": ["s4"]}]}},
]
MEMBERS = {"A": {"s1", "s2"}, "B": {"s3"}, "C": {"s4"}}


def test_reopening_restores_tabs_only_when_the_setting_is_on():
    on = restore(SAVED, MEMBERS, current="A", reopen_tabs=True)
    assert [w.current for w in on] == ["A", "C"]
    assert on[0].tabs["A"] == [TabLayout(["s1", "s2"], Orientation.VERTICAL)]
    assert on[0].tabs["B"] == [TabLayout(["s3"])]
    off = restore(SAVED, MEMBERS, current="C", reopen_tabs=False)
    assert off == [WindowLayout("C", {})]


def test_a_saved_tab_of_a_session_no_longer_a_member_is_dropped():
    members = {"A": {"s2"}, "B": set(), "C": {"s4"}}
    windows = restore(SAVED, members, current="A", reopen_tabs=True)
    assert windows[0].tabs["A"] == [TabLayout(["s2"], Orientation.VERTICAL)]
    assert windows[0].tabs.get("B", []) == []


def test_a_project_saved_in_two_windows_is_restored_in_the_first_and_unknown_ones_go():
    saved = [*SAVED, {"current": "A", "tabs": {"A": [{"panes": ["s1"]}]}}, {"current": "gone", "tabs": {}}]
    windows = restore(saved, MEMBERS, current="A", reopen_tabs=True)
    assert [w.current for w in windows] == ["A", "C"]


def test_garbage_in_the_saved_windows_falls_back_to_one_window():
    assert restore(["x", {"current": 3}], MEMBERS, current="B", reopen_tabs=True) == [WindowLayout("B", {})]


def test_the_layout_round_trips_through_its_saved_form(layouts):
    layouts.open(1, "A", "s1")
    layouts.open_beside(1, "A", 0, "s2")
    layouts.set_orientation(1, "A", 0, Orientation.VERTICAL)
    layouts.add_window(2, "C")
    layouts.open(2, "C", "s4")
    saved = layouts.to_list()
    assert restore(saved, MEMBERS, current="A", reopen_tabs=True) == list(layouts.windows.values())
