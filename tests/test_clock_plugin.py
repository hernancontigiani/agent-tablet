from datetime import datetime, timedelta, timezone

import pytest

from agent_tablet import clock
from tests import clock_plugin


def test_no_variable_no_shift():
    assert clock_plugin.instant_from({}) is None
    assert clock_plugin.start_travel({}) is None


def test_the_shift_moves_python_s_clock():
    instant = datetime(2026, 11, 6, 23, 30, tzinfo=timezone(timedelta(hours=-3)))
    travel = clock_plugin.start_travel({clock_plugin.ENV: instant.isoformat()})
    assert travel is not None
    try:
        seen = clock.now().astimezone()
        assert abs(seen - instant) < timedelta(minutes=1), seen
    finally:
        travel.stop()


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("tomorrow at midnight", id="not-iso"),
        pytest.param("2026-11-06T23:30:00", id="no-offset"),
    ],
)
def test_a_malformed_instant_stops_the_run_with_its_value(value):
    with pytest.raises(pytest.UsageError, match=value):
        clock_plugin.instant_from({clock_plugin.ENV: value})
