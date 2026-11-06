"""The one place logging is configured. Every other module only does
`log = logging.getLogger(__name__)` and passes identifiers in `extra={...}`, never in the message:

    log.warning("could not read transcript", extra={"session_id": sid, "path": str(path)})

Records go to stderr, which the desktop session's journal keeps when the app is started from its
launcher. AGENT_TABLET_LOG=debug|info|warning|error sets the level; warning by default.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from typing import TextIO

ENV = "AGENT_TABLET_LOG"
_LOGGER = "agent_tablet"
# What every LogRecord carries; anything else on a record came in through `extra`.
_STANDARD = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class _Formatter(logging.Formatter):
    """`LEVEL logger: message key=value ...` — the identifiers from `extra`, sorted by key."""

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = {key: value for key, value in vars(record).items() if key not in _STANDARD}
        if extras:
            line += " " + " ".join(f"{key}={value!r}" for key, value in sorted(extras.items()))
        return line


def configure(environ: Mapping[str, str], stream: TextIO | None = None) -> logging.Logger:
    """Set up the app's logger once; calling it again replaces the handler instead of adding one."""
    logger = logging.getLogger(_LOGGER)
    name = environ.get(ENV, "warning").upper()
    level = logging.getLevelNamesMapping().get(name, logging.WARNING)
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(_Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    return logger
