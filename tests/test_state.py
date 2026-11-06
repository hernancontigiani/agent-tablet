import json

import pytest


def test_roundtrip(app_state):
    state = app_state.AppState()
    state.set_name("sid-1", "My session")
    state.set_hidden("sid-2", True)
    state.set_setting("scrollback", 5000)

    fresh = app_state.AppState()
    assert fresh.get_name("sid-1") == "My session"
    assert fresh.is_hidden("sid-2")
    assert fresh.get_setting("scrollback") == 5000


def test_clearing_name_removes_entry(app_state):
    state = app_state.AppState()
    state.set_name("sid-1", "Name")
    state.set_name("sid-1", "   ")
    assert app_state.AppState().get_name("sid-1") is None


def test_favorites_leave_state_json_on_the_next_save(app_state):
    """Projects replace favorites; the ones already saved are dropped, not migrated (plan 04)."""
    app_state._CONFIG_DIR.mkdir(parents=True)
    app_state._STATE_FILE.write_text(json.dumps({"names": {"a": "x"}, "favorites": ["a"]}), encoding="utf-8")
    state = app_state.AppState()
    state.set_name("b", "y")
    saved = json.loads(app_state._STATE_FILE.read_text(encoding="utf-8"))
    assert "favorites" not in saved
    assert saved["names"] == {"a": "x", "b": "y"}


def test_defaults_for_unknown_settings(app_state):
    state = app_state.AppState()
    assert state.get_setting("color_scheme") == "system"
    assert state.get_setting("font") == ""


def test_corrupt_state_file_recovers(app_state):
    state = app_state.AppState()
    state.set_name("sid", "x")  # creates the file
    app_state._STATE_FILE.write_text("{corrupt", encoding="utf-8")
    fresh = app_state.AppState()  # must not raise
    assert fresh.get_name("sid") is None


def _write_original_state(directory, names):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "state.json").write_text(
        json.dumps({"names": names, "favorites": list(names)}), encoding="utf-8"
    )


@pytest.mark.parametrize("which", [0, 1], ids=["agent-session-manager", "pre-rebrand-claude-session-manager"])
def test_imports_the_original_apps_state_once(app_state, which):
    original = app_state._ORIGINAL_CONFIG_DIRS[which]
    _write_original_state(original, {"sid": "Carried over"})
    before = (original / "state.json").read_bytes()

    state = app_state.AppState()
    assert state.get_name("sid") == "Carried over"
    assert app_state._STATE_FILE.exists()  # copied into our own location
    assert (original / "state.json").read_bytes() == before  # the original's file is never written


def test_the_original_apps_current_name_wins_over_its_pre_rebrand_name(app_state):
    newest, oldest = app_state._ORIGINAL_CONFIG_DIRS
    _write_original_state(oldest, {"sid": "Old"})
    _write_original_state(newest, {"sid": "New"})
    assert app_state.AppState().get_name("sid") == "New"


def test_own_state_is_never_replaced_by_the_original_apps(app_state):
    _write_original_state(app_state._ORIGINAL_CONFIG_DIRS[0], {"sid": "Original"})
    app_state._CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    app_state._STATE_FILE.write_text(json.dumps({"names": {"sid": "Ours"}}), encoding="utf-8")
    assert app_state.AppState().get_name("sid") == "Ours"


def test_migrates_legacy_names_file(app_state):
    app_state._LEGACY_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    app_state._LEGACY_NAMES_FILE.write_text(json.dumps({"old-sid": "Old name"}), encoding="utf-8")
    state = app_state.AppState()
    assert state.get_name("old-sid") == "Old name"


def test_projects_live_next_to_state_json(app_state):
    state = app_state.AppState()
    assert [p.name for p in state.projects.projects] == ["Default"]
    state.projects.add(state.projects.current, "s1")
    state.save_projects()
    assert (app_state._CONFIG_DIR / "projects.json").exists()
    assert app_state.AppState().projects.projects[0].members == ["s1"]
