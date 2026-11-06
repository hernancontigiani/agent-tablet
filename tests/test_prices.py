from datetime import UTC, datetime

import pytest

from agent_tablet import prices

WHEN = datetime(2026, 11, 6, tzinfo=UTC)
MILLION = 1_000_000


def test_cost_prices_each_token_kind():
    # Opus 5.5: $4 input, $5 5-minute write, $8 1-hour write, $0.20 read, $20 output, per million.
    cost = prices.cost(
        "claude-opus-5-5",
        WHEN,
        input=MILLION,
        output=MILLION,
        cache_write=2 * MILLION,
        cache_write_1h=MILLION,
        cache_read=MILLION,
    )
    assert cost == pytest.approx(4 + 20 + 5 + 8 + 0.20)


def test_one_hour_cache_writes_cost_twice_input():
    for model in ("claude-opus-5-5", "claude-opus-4-8", "claude-sonnet-5-5", "claude-haiku-4-5"):
        price = prices.price_for(model, WHEN)
        assert price is not None, model
        assert price.cache_write_1h == pytest.approx(2 * price.input), model


def test_an_unknown_model_has_tokens_but_no_price():
    assert prices.cost("claude-imaginary-9", WHEN, input=MILLION, output=0) is None


@pytest.mark.parametrize(
    ("model_id", "row"),
    [
        ("claude-opus-5-5", "claude-opus-5-5"),
        ("claude-opus-5", "claude-opus-5"),
        ("claude-fable-5-1", "claude-fable-5-1"),
        ("claude-sonnet-4-5-20250929", "claude-sonnet-4-5"),  # a dated id
        ("claude-opus-5-5[1m]", "claude-opus-5-5"),  # the 1M window is priced the same
    ],
)
def test_a_model_id_finds_its_row(model_id, row):
    assert prices.price_for(model_id, WHEN) == prices.price_for(row, WHEN)
    assert prices.price_for(row, WHEN) is not None


def test_haiku_5_5_pays_the_higher_rate_over_100k_prompt_tokens():
    small = prices.cost("claude-haiku-5-5", WHEN, input=50_000, output=0)
    # The prompt counts input plus cache reads and writes: 1 + 100k reads crosses the threshold.
    large = prices.cost("claude-haiku-5-5", WHEN, input=1, output=0, cache_read=100_000)
    assert small == pytest.approx(0.10 * 50_000 / MILLION)
    assert large == pytest.approx(0.50 / MILLION + 0.05 * 100_000 / MILLION)


def test_the_table_says_where_and_when_it_was_copied():
    assert prices.SOURCE.startswith("https://")
    assert prices.COPIED == "2026-11-06"
    assert len(prices.TABLE) >= 15
