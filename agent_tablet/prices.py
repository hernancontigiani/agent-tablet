"""List prices per million tokens, copied from Anthropic's published pricing.

An estimate, not a bill: a subscription is not billed per token, and this table is only as current
as the date below. The app makes no network connections, so a price change means editing this
table: add a row with the day it took effect, keep the old one, and each entry is priced at the
rate in force on its own date.

The 1M-token context window is priced at the standard rate on the models that have it, so a
`[1m]` model id prices as its base model. Claude Haiku 5.5 is priced per request by prompt size:
over 100,000 prompt tokens (input + cache reads + cache writes) it pays its second row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
COPIED = "2026-11-06"
_SINCE = date(2000, 1, 1)  # rows copied without a known start apply to every earlier entry
HAIKU_5_5_LONG_PROMPT = 100_000


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float
    output: float


def _p(input_: float, write_5m: float, write_1h: float, read: float, output: float) -> Price:
    return Price(input_, write_5m, write_1h, read, output)


# model -> [(in force since, price)], newest last. Copied from SOURCE on COPIED.
TABLE: dict[str, list[tuple[date, Price]]] = {
    "claude-fable-5-1": [(_SINCE, _p(10, 12.50, 20, 0.25, 50))],
    "claude-mythos-5-1": [(_SINCE, _p(10, 12.50, 20, 0.25, 50))],
    "claude-fable-5": [(_SINCE, _p(10, 12.50, 20, 1, 50))],
    "claude-mythos-5": [(_SINCE, _p(10, 12.50, 20, 1, 50))],
    "claude-opus-5-5": [(_SINCE, _p(4, 5, 8, 0.20, 20))],
    "claude-opus-5": [(_SINCE, _p(5, 6.25, 10, 0.50, 25))],
    "claude-opus-4-8": [(_SINCE, _p(5, 6.25, 10, 0.50, 25))],
    "claude-opus-4-7": [(_SINCE, _p(5, 6.25, 10, 0.50, 25))],
    "claude-opus-4-6": [(_SINCE, _p(5, 6.25, 10, 0.50, 25))],
    "claude-opus-4-5": [(_SINCE, _p(5, 6.25, 10, 0.50, 25))],
    "claude-opus-4-1": [(_SINCE, _p(15, 18.75, 30, 1.50, 75))],
    "claude-opus-4": [(_SINCE, _p(15, 18.75, 30, 1.50, 75))],
    "claude-sonnet-5-5": [(_SINCE, _p(2, 2.50, 4, 0.10, 10))],
    "claude-sonnet-5": [(_SINCE, _p(2, 2.50, 4, 0.20, 10))],
    "claude-sonnet-4-6": [(_SINCE, _p(3, 3.75, 6, 0.30, 15))],
    "claude-sonnet-4-5": [(_SINCE, _p(3, 3.75, 6, 0.30, 15))],
    "claude-sonnet-4": [(_SINCE, _p(3, 3.75, 6, 0.30, 15))],
    "claude-haiku-5-5": [(_SINCE, _p(0.10, 0.125, 0.20, 0.01, 0.50))],
    "claude-haiku-4-5": [(_SINCE, _p(1, 1.25, 2, 0.10, 5))],
}
_HAIKU_5_5_LONG = _p(0.50, 0.625, 1, 0.05, 2.50)

_DATED = re.compile(r"-\d{8}$")


def _row(model: str) -> str:
    return _DATED.sub("", model.removesuffix("[1m]"))


def price_for(model: str, when: datetime) -> Price | None:
    rows = TABLE.get(_row(model))
    if not rows:
        return None
    day = when.date()
    in_force = [price for since, price in rows if since <= day]
    return in_force[-1] if in_force else rows[0][1]


def cost(
    model: str,
    when: datetime,
    *,
    input: int,
    output: int,
    cache_write: int = 0,
    cache_write_1h: int = 0,
    cache_read: int = 0,
) -> float | None:
    """USD for one request's tokens, or None for a model the table does not know."""
    price = price_for(model, when)
    if price is None:
        return None
    if _row(model) == "claude-haiku-5-5" and input + cache_write + cache_read > HAIKU_5_5_LONG_PROMPT:
        price = _HAIKU_5_5_LONG
    write_5m = max(0, cache_write - cache_write_1h)
    return (
        input * price.input
        + output * price.output
        + write_5m * price.cache_write_5m
        + cache_write_1h * price.cache_write_1h
        + cache_read * price.cache_read
    ) / 1_000_000
