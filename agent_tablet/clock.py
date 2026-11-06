"""The one place the app reads the time, so a test can move it."""

from __future__ import annotations

import time
from datetime import datetime


def now() -> datetime:
    """Local wall-clock time, naive, as the transcripts' timestamps are compared against."""
    return datetime.now()


def monotonic() -> float:
    """Seconds on a clock that never jumps: for measuring how long something took."""
    return time.monotonic()
