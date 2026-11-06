import ast
import io
import logging
from pathlib import Path

import pytest

from agent_tablet import log

PACKAGE = Path(__file__).resolve().parent.parent / "agent_tablet"


@pytest.fixture
def captured():
    stream = io.StringIO()
    yield stream
    logging.getLogger("agent_tablet").handlers = []


def test_identifiers_from_extra_reach_the_line_sorted_by_key(captured):
    log.configure({}, stream=captured)
    logging.getLogger("agent_tablet.store").warning(
        "could not read transcript", extra={"session_id": "abc", "path": "/tmp/x.jsonl"}
    )
    assert captured.getvalue() == (
        "WARNING agent_tablet.store: could not read transcript path='/tmp/x.jsonl' session_id='abc'\n"
    )


@pytest.mark.parametrize(
    ("value", "shown", "hidden"),
    [
        pytest.param(None, "warning", "info", id="default-warning"),
        pytest.param("debug", "debug", None, id="debug"),
        pytest.param("ERROR", "error", "warning", id="any-case"),
        pytest.param("loud", "warning", "info", id="unknown-falls-back"),
    ],
)
def test_the_level_comes_from_the_environment(captured, value, shown, hidden):
    environ = {} if value is None else {log.ENV: value}
    log.configure(environ, stream=captured)
    logger = logging.getLogger("agent_tablet.x")
    getattr(logger, shown)("shown")
    if hidden is not None:
        getattr(logger, hidden)("hidden")
    assert "shown" in captured.getvalue()
    assert "hidden" not in captured.getvalue()


def test_configuring_twice_does_not_print_twice(captured):
    log.configure({}, stream=captured)
    log.configure({}, stream=captured)
    logging.getLogger("agent_tablet").warning("once")
    assert captured.getvalue().count("once") == 1


def test_only_log_py_configures_logging():
    """A second basicConfig or handler elsewhere prints every record twice, or not at all."""
    modules = sorted(PACKAGE.glob("*.py"))
    assert len(modules) >= 25  # a walk over nothing passes
    offenders = []
    for path in modules:
        if path.name == "log.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"basicConfig", "addHandler", "setLevel"}
            ):
                offenders.append(f"{path.name}:{node.lineno} {node.func.attr}()")
    assert offenders == []
