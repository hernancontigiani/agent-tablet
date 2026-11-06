"""Rules about the shape of the code, checked on its AST: a grep is fooled by comments and strings."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "agent_tablet"


def _modules() -> list[tuple[Path, ast.Module]]:
    modules = [(path, ast.parse(path.read_text(encoding="utf-8"))) for path in sorted(PACKAGE.glob("*.py"))]
    assert len(modules) >= 25  # a walk over nothing passes
    return modules


def _binds_underscore(node: ast.AST) -> bool:
    match node:
        case ast.Name(id="_", ctx=ast.Store()):
            return True
        case ast.arg(arg="_"):
            return True
    return False


def _own_scope(function: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
    """The nodes of a function's body, without descending into nested functions or classes."""
    stack = list(ast.iter_child_nodes(function))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            stack.extend(ast.iter_child_nodes(node))


def test_no_function_that_translates_rebinds_the_translation_function():
    """`variant_key, _, session_id = ...` in a function that later calls `_("...")` turns the
    translation into a call on a string, which raises only when that line runs."""
    offenders = []
    for path, module in _modules():
        for function in ast.walk(module):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                continue
            scope = list(_own_scope(function))
            translates = any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"
                for node in scope
            )
            if translates and any(_binds_underscore(node) for node in scope):
                offenders.append(f"{path.name}:{function.lineno}")
    assert offenders == []


def test_a_location_without_a_local_path_is_refused_with_a_message(tmp_path, monkeypatch):
    from gi.repository import Gio

    from agent_tablet import dialogs

    shown = []
    monkeypatch.setattr(dialogs, "error_dialog", lambda parent, heading, body: shown.append(heading))

    remote = Gio.File.new_for_uri("sftp://example.invalid/home/someone/project")
    assert dialogs.require_local_path(remote, parent=None, heading="Choose a local folder") is None
    assert shown == ["Choose a local folder"]

    local = Gio.File.new_for_path(str(tmp_path))
    assert dialogs.require_local_path(local, parent=None, heading="Choose a local folder") == str(tmp_path)
    assert shown == ["Choose a local folder"]  # no second message


_CLOCK_READS = {
    ("datetime", "now"),
    ("datetime", "today"),
    ("date", "today"),
    ("time", "time"),
    ("time", "monotonic"),
    ("GLib", "get_real_time"),
}


def test_nothing_reads_the_clock_outside_clock_py():
    """Time windows ("idle for 5 minutes", cost per day) must be testable at 23:59 and across
    midnight, which takes one clock a test can move."""
    offenders = []
    for path, module in _modules():
        if path.name == "clock.py":
            continue
        for node in ast.walk(module):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and (node.func.value.id, node.func.attr) in _CLOCK_READS
            ):
                offenders.append(f"{path.name}:{node.lineno} {node.func.value.id}.{node.func.attr}()")
    assert offenders == []


def test_the_suite_never_sees_the_real_home():
    import os
    import pwd

    from agent_tablet import state

    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for seen in (Path.home(), state._CONFIG_BASE):
        assert not seen.is_relative_to(real_home), seen
        assert "agent-tablet-tests-" in str(seen), seen


def test_projects_and_layout_stay_free_of_gtk():
    """Membership, tabs and windows are decided in plain data, so every rule about them is tested
    without a display; the widgets only show what these modules decide."""
    offenders = []
    for path, module in _modules():
        if path.name not in ("projects.py", "layout.py"):
            continue
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            offenders += [f"{path.name}:{node.lineno} {n}" for n in names if n.split(".")[0] == "gi"]
    assert offenders == []
