"""Projects: a name and the sessions the user put in it, saved as JSON (plan 04)."""

import json

import pytest

from agent_tablet.projects import (
    DEFAULT_NAME,
    ProjectError,
    Projects,
    blocked_elsewhere,
    folder_labels,
    joins_project,
    validate_new_session,
)
from agent_tablet.sessions import session_from_file
from tests.conftest import make_transcript_lines


@pytest.fixture
def path(tmp_path):
    return tmp_path / "config" / "agent-tablet" / "projects.json"


def _two_projects() -> Projects:
    projects = Projects.fresh()
    projects.create("Core")
    return projects


def test_a_missing_projects_file_starts_with_an_empty_default(path):
    projects = Projects.load(path)
    assert [p.name for p in projects.projects] == [DEFAULT_NAME]
    assert projects.projects[0].members == []
    assert projects.current == projects.projects[0].id
    assert projects.broken is None


def test_adding_a_session_from_another_project_moves_it():
    projects = _two_projects()
    default, core = projects.projects
    assert projects.add(default.id, "s1") is None
    previous = projects.add(core.id, "s1")
    assert previous is default
    assert default.members == []
    assert core.members == ["s1"]
    assert projects.owner("s1") is core


def test_adding_a_session_twice_to_its_own_project_changes_nothing():
    projects = Projects.fresh()
    default = projects.projects[0]
    projects.add(default.id, "s1")
    assert projects.add(default.id, "s1") is None
    assert default.members == ["s1"]


@pytest.mark.parametrize(
    ("name", "accepted"),
    [
        pytest.param(" core ", False, id="same-name-other-case-and-spaces"),
        pytest.param("", False, id="empty"),
        pytest.param("   ", False, id="only-spaces"),
        pytest.param("Core 2", True, id="a-different-name"),
    ],
)
def test_a_project_name_is_unique_ignoring_case_and_spaces(name, accepted):
    projects = _two_projects()
    if accepted:
        assert projects.create(name).name == name.strip()
    else:
        with pytest.raises(ProjectError):
            projects.create(name)
        assert len(projects.projects) == 2


def test_renaming_keeps_the_name_unique_but_allows_its_own():
    projects = _two_projects()
    core = projects.projects[1]
    projects.rename(core.id, "CORE")
    assert core.name == "CORE"
    with pytest.raises(ProjectError):
        projects.rename(core.id, DEFAULT_NAME.lower())


def test_the_last_project_cannot_be_deleted_and_deleting_releases_its_sessions():
    projects = Projects.fresh()
    with pytest.raises(ProjectError):
        projects.delete(projects.projects[0].id)
    core = projects.create("Core")
    projects.add(core.id, "s1")
    projects.current = core.id
    released = projects.delete(core.id)
    assert released == ["s1"]
    assert projects.owner("s1") is None
    assert [p.name for p in projects.projects] == [DEFAULT_NAME]
    assert projects.current == projects.projects[0].id  # the deleted one was current


def test_a_group_disappears_when_its_last_session_leaves():
    projects = Projects.fresh()
    default = projects.projects[0]
    for sid in ("s1", "s2"):
        projects.add(default.id, sid)
    projects.new_group(default.id, "pair", "s1")
    projects.set_group(default.id, "s2", "pair")
    assert [g.members for g in default.groups] == [["s1", "s2"]]
    projects.set_group(default.id, "s1", None)
    projects.remove(default.id, "s2")
    assert default.groups == []


def test_groups_get_their_colors_in_turn_and_list_first():
    projects = Projects.fresh()
    default = projects.projects[0]
    for sid in ("s1", "s2", "s3"):
        projects.add(default.id, sid)
    first = projects.new_group(default.id, "a", "s2")
    second = projects.new_group(default.id, "b", "s3")
    assert first.color != second.color
    rows = projects.rows(default.id)
    assert [(g.name if g else None, ids) for g, ids in rows] == [("a", ["s2"]), ("b", ["s3"]), (None, ["s1"])]


def test_removing_a_session_leaves_its_transcript_byte_for_byte(projects_dir):
    root, ids = projects_dir
    transcript = next(root.glob(f"*/{ids['alpha1']}.jsonl"))
    before = transcript.read_bytes()
    projects = Projects.fresh()
    default = projects.projects[0]
    projects.add(default.id, ids["alpha1"])
    projects.remove(default.id, ids["alpha1"])
    projects.delete(projects.create("Other").id)
    assert transcript.read_bytes() == before


def test_saving_writes_the_whole_file_through_a_temporary(path, monkeypatch):
    projects = _two_projects()
    projects.add(projects.projects[1].id, "s1")
    projects.save(path)
    assert json.loads(path.read_text(encoding="utf-8"))["projects"][1]["members"] == ["s1"]
    assert [p.name for p in path.parent.iterdir()] == ["projects.json"]  # no temporary left

    before = path.read_bytes()
    projects.add(projects.projects[0].id, "s2")

    def fail(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(type(path), "replace", fail)
    with pytest.raises(OSError):
        projects.save(path)
    assert path.read_bytes() == before


def test_a_saved_file_loads_back_the_same(path):
    projects = _two_projects()
    core = projects.projects[1]
    projects.add(core.id, "s1")
    projects.new_group(core.id, "pair", "s1")
    projects.current = core.id
    projects.save(path)
    again = Projects.load(path)
    assert again.to_dict() == projects.to_dict()


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("{", id="not-json"),
        pytest.param('{"version": 1, "projects": "x"}', id="wrong-shape"),
        pytest.param('{"version": 1, "projects": []}', id="no-project"),
        pytest.param(
            '{"version": 99, "projects": [{"id": "a", "name": "A", "members": []}]}', id="newer-version"
        ),
    ],
)
def test_an_unreadable_projects_file_is_kept_aside_and_default_starts(path, content):
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    projects = Projects.load(path)
    broken = path.with_name("projects.json.broken")
    assert projects.broken == broken
    assert broken.read_text(encoding="utf-8") == content
    assert not path.exists()
    assert [p.name for p in projects.projects] == [DEFAULT_NAME]


def test_unknown_keys_in_a_project_survive_a_round_trip(path):
    path.parent.mkdir(parents=True)
    data = {
        "version": 1,
        "current": "a",
        "projects": [{"id": "a", "name": "A", "members": ["s1"], "groups": [], "folders": ["/x"]}],
        "theme": "later",
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    Projects.load(path).save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["projects"][0]["folders"] == ["/x"]
    assert saved["theme"] == "later"


def test_a_session_listed_in_two_projects_by_hand_stays_in_the_first(path):
    path.parent.mkdir(parents=True)
    data = {
        "version": 1,
        "current": "b",
        "projects": [
            {"id": "a", "name": "A", "members": ["s1"]},
            {"id": "b", "name": "B", "members": ["s1", "s2"]},
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    projects = Projects.load(path)
    assert [p.members for p in projects.projects] == [["s1"], ["s2"]]


@pytest.mark.parametrize(
    ("cwds", "expected"),
    [
        pytest.param(
            {"s1": "/a/guardian", "s2": "/b/fabric"},
            {"s1": "guardian", "s2": "fabric"},
            id="mixed-shows-names",
        ),
        pytest.param({"s1": "/a/guardian", "s2": "/a/guardian"}, {"s1": "", "s2": ""}, id="shared-is-hidden"),
        pytest.param(
            {"s1": "/a/guardian", "s2": None}, {"s1": "", "s2": ""}, id="one-known-folder-is-shared"
        ),
        pytest.param(
            {"s1": "/a/guardian", "s2": "/b/fabric", "s3": None},
            {"s1": "guardian", "s2": "fabric", "s3": ""},
            id="unknown-folder-has-no-label",
        ),
    ],
)
def test_the_folder_label_is_the_name_and_hidden_when_shared(cwds, expected):
    assert folder_labels(cwds) == expected


def test_the_blocked_count_counts_only_other_projects():
    projects = _two_projects()
    default, core = projects.projects
    for sid in ("a1", "a2"):
        projects.add(default.id, sid)
    for sid in ("b1", "b2", "b3"):
        projects.add(core.id, sid)
    states = {"a1": "blocked", "a2": "working", "b1": "blocked", "b2": "blocked", "b3": "idle"}
    assert blocked_elsewhere(projects, default.id, states) == 2
    assert blocked_elsewhere(projects, core.id, states) == 1


def test_a_session_joins_its_project_only_after_a_user_message(tmp_path):
    title_only = [{"type": "custom-title", "customTitle": "x", "sessionId": "s"}]
    path = tmp_path / "s.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in title_only), encoding="utf-8")
    session = session_from_file(path)
    assert session is not None
    assert not joins_project(session)
    lines = title_only + make_transcript_lines("/p", "hello")
    path.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
    session = session_from_file(path)
    assert session is not None
    assert joins_project(session)


@pytest.mark.parametrize(
    ("name", "folder", "ok"),
    [
        pytest.param("", "exists", False, id="no-name"),
        pytest.param("   ", "exists", False, id="blank-name"),
        pytest.param("lm-plan", "missing", False, id="missing-folder"),
        pytest.param("lm-plan", None, False, id="no-folder-chosen"),
        pytest.param("lm-plan", "exists", True, id="name-and-folder"),
    ],
)
def test_a_new_session_needs_a_name_and_a_folder(tmp_path, name, folder, ok):
    (tmp_path / "exists").mkdir()
    error = validate_new_session(name, str(tmp_path / folder) if folder else "")
    assert (error is None) == ok


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param("HOME/git/agent-tablet", ("agent-tablet", "~/git"), id="under-home"),
        pytest.param("HOME/marvik/ccai/guardian", ("guardian", "~/marvik/ccai"), id="deeper"),
        pytest.param("/srv/data", ("data", "/srv"), id="outside-home"),
    ],
)
def test_a_folder_is_offered_by_its_name_then_where_it_is(path, expected):
    """In the New page's folder list, full paths cut at the end all start alike."""
    from pathlib import Path

    from agent_tablet.addsession import folder_parts

    assert folder_parts(path.replace("HOME", str(Path.home()))) == expected


def test_the_folders_to_start_in_come_most_recent_first(tmp_path):
    from agent_tablet.addsession import recent_folders
    from agent_tablet.sessions import Session

    def session(cwd, mtime):
        return Session(session_id=str(mtime), jsonl_path=tmp_path / "x", cwd=cwd, preview="", mtime=mtime)

    sessions = [session("/a", 10.0), session("/b", 30.0), session("/a", 20.0), session(None, 99.0)]
    assert recent_folders(sessions) == ["/b", "/a"]
