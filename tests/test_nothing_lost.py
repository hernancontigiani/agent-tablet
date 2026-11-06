import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "docs" / "history" / "nothing_lost.py"
_spec = importlib.util.spec_from_file_location("nothing_lost", _SCRIPT)
assert _spec is not None and _spec.loader is not None
nothing_lost = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nothing_lost)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")
    (tmp_path / "CLAUDE.md").write_text("# Rules\n\n- Keep A.\n- Keep B.\n", encoding="utf-8")
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "00-STATUS.md").write_text("| 1 | Plan 01 | In flight |\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("CLAUDE.md", "docs/history/root/CLAUDE.md"),
        ("plans/00-STATUS.md", "docs/history/plans/00-STATUS.md"),
        ("docs/NOT_BUILT_YET.md", "docs/history/NOT_BUILT_YET.md"),
        ("plans/01-some-plan.md", None),  # a plan dies on delivery; its exit is its header
        ("README.md", None),
        ("docs/history/root/CLAUDE.md", None),  # the history has no history
    ],
)
def test_each_decision_document_has_one_mirror(relative, expected):
    assert nothing_lost.mirror_of(relative) == expected


def test_a_removed_line_missing_from_the_mirror_is_reported(repo):
    _write(repo / "CLAUDE.md", "# Rules\n\n- Keep A.\n")
    problems = nothing_lost.check(repo, "CLAUDE.md")
    assert problems == ["CLAUDE.md:4: not in docs/history/root/CLAUDE.md: - Keep B."]


def test_a_removed_line_copied_to_the_mirror_passes(repo):
    _write(repo / "CLAUDE.md", "# Rules\n\n- Keep A.\n")
    _write(repo / "docs/history/root/CLAUDE.md", "## Rules\n\n> Left on 2026-11-05.\n- Keep B.\n")
    assert nothing_lost.check(repo, "CLAUDE.md") == []


def test_a_mirror_that_loses_a_line_is_reported(repo):
    _write(repo / "docs/history/plans/00-STATUS.md", "> Left on 2026-11-05.\n| 0 | Plan 00 | Delivered |\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "mirror")
    _write(repo / "docs/history/plans/00-STATUS.md", "> Left on 2026-11-05.\n")
    problems = nothing_lost.check(repo, "plans/00-STATUS.md")
    assert problems == [
        "docs/history/plans/00-STATUS.md:2: the mirror lost a line: | 0 | Plan 00 | Delivered |"
    ]


def test_blank_and_markup_lines_need_no_mirror(repo):
    # Drops the title and the blank line under it: only the title needs the mirror.
    _write(repo / "CLAUDE.md", "- Keep A.\n- Keep B.\n")
    problems = nothing_lost.check(repo, "CLAUDE.md")
    assert problems == ["CLAUDE.md:1: not in docs/history/root/CLAUDE.md: # Rules"]


def test_every_mirrored_document_in_the_tree_is_found(repo):
    _write(repo / "docs/NOT_BUILT_YET.md", "# Deferred\n")
    _git(repo, "add", ".")
    found = nothing_lost.mirrored_documents(repo)
    assert len(found) >= 3
    assert found == ["CLAUDE.md", "docs/NOT_BUILT_YET.md", "plans/00-STATUS.md"]
