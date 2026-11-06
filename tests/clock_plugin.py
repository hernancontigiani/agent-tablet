"""Moves Python's clock for the whole run when AT_TEST_CLOCK_AT is set.

`AT_TEST_CLOCK_AT=<ISO instant> TZ=UTC uv run pytest -n auto` runs every test as if it were that
moment, ticking from there: it finds the tests that pass only away from midnight. Each xdist worker
runs pytest_configure, so each starts its own travel. It does not replace injecting the time
(agent_tablet/clock.py); it finds where that was forgotten.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime

import pytest

ENV = "AT_TEST_CLOCK_AT"
_travel = None


def instant_from(environ: Mapping[str, str]) -> datetime | None:
    value = environ.get(ENV, "")
    if not value:
        return None
    try:
        instant = datetime.fromisoformat(value)
    except ValueError:
        raise pytest.UsageError(f"{ENV}={value!r} is not an ISO 8601 instant") from None
    if instant.tzinfo is None:
        raise pytest.UsageError(f"{ENV}={value!r} needs its UTC offset, e.g. 2026-11-06T23:30:00-03:00")
    return instant


def start_travel(environ: Mapping[str, str]):
    instant = instant_from(environ)
    if instant is None:
        return None
    import time_machine

    travel = time_machine.travel(instant, tick=True)
    travel.start()
    return travel


def pytest_configure(config: pytest.Config) -> None:
    global _travel
    _travel = start_travel(os.environ)


def pytest_unconfigure(config: pytest.Config) -> None:
    if _travel is not None:
        _travel.stop()
