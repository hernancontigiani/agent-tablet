import json
from pathlib import Path

import pytest

from agent_tablet import claudesettings, integrations

THEIRS = {"type": "command", "command": "~/bin/my-bar.sh", "padding": 1}


def _settings_file() -> Path:
    path = integrations.user_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write(data) -> Path:
    path = _settings_file()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _read() -> dict:
    return json.loads(integrations.user_settings_path().read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clean():
    """Each test starts with no settings file and no record (the suite's HOME is a temp dir)."""
    for path in (integrations.user_settings_path(), integrations.record_path()):
        path.unlink(missing_ok=True)


def test_installing_changes_only_status_line():
    before = {"model": "opus", "hooks": {"Stop": []}, "permissions": {"allow": ["Bash(ls)"]}}
    _write(before)
    integrations.install_statusline()
    after = _read()
    assert after["statusLine"] == claudesettings.settings()["statusLine"]
    assert {key: value for key, value in after.items() if key != "statusLine"} == before
    assert integrations.statusline_installed()


def test_removing_restores_the_previous_status_line_exactly():
    _write({"model": "opus", "statusLine": THEIRS})
    integrations.install_statusline()
    integrations.remove_statusline()
    assert _read() == {"model": "opus", "statusLine": THEIRS}
    assert not integrations.statusline_installed()


def test_removing_when_there_was_none_removes_the_key():
    _write({"model": "opus"})
    integrations.install_statusline()
    integrations.remove_statusline()
    assert _read() == {"model": "opus"}


def test_removing_leaves_a_file_the_human_changed_since():
    _write({"model": "opus"})
    integrations.install_statusline()
    changed = {"model": "opus", "statusLine": {"type": "command", "command": "their-new-bar"}}
    _write(changed)
    with pytest.raises(integrations.IntegrationError):
        integrations.remove_statusline()
    assert _read() == changed


def test_installing_twice_writes_once():
    _write({"model": "opus"})
    integrations.install_statusline()
    first = integrations.user_settings_path().stat().st_mtime_ns
    integrations.install_statusline()
    assert integrations.user_settings_path().stat().st_mtime_ns == first


@pytest.mark.parametrize("content", ["[1, 2]", "not json"], ids=["a-list", "not-json"])
def test_a_settings_file_that_is_not_an_object_is_refused(content):
    path = _settings_file()
    path.write_text(content, encoding="utf-8")
    with pytest.raises(integrations.IntegrationError):
        integrations.install_statusline()
    assert path.read_text(encoding="utf-8") == content


def test_installing_keeps_a_backup_of_the_file_as_it_was():
    _write({"model": "opus", "statusLine": THEIRS})
    integrations.install_statusline()
    backups = list(integrations.backup_dir().iterdir())
    assert backups
    assert json.loads(max(backups).read_text(encoding="utf-8")) == {"model": "opus", "statusLine": THEIRS}


def test_a_missing_settings_file_is_created_with_only_the_status_line():
    integrations.install_statusline()
    assert _read() == {"statusLine": claudesettings.settings()["statusLine"]}


def test_the_human_s_own_status_line_is_what_gets_chained():
    assert integrations.chained_command() is None
    _write({"statusLine": THEIRS})
    assert integrations.chained_command() == "~/bin/my-bar.sh"  # under --settings, theirs is hidden
    integrations.install_statusline()
    assert integrations.chained_command() == "~/bin/my-bar.sh"  # installed: the one it replaced
