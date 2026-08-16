from datetime import datetime, timezone
from typing import Any

from openhedge_core.embeddings import market_embedding_text
from openhedge_core.types.market import Market, MarketSource


def _market(**overrides: Any) -> Market:
    values: dict[str, Any] = {
        "source": MarketSource.KALSHI,
        "ticker": "MKT-ACTIVE",
        "event_ticker": "EVT-OPEN",
        "event_title": "Will the bill pass?",
        "series_ticker": "SERIES",
        "strike_order": 0,
        "url": "https://kalshi.com/markets/SERIES/EVT-OPEN?op_market_ticker=MKT-ACTIVE",
        "category": "Politics",
        "tags": ["elections"],
        "question": "should not appear in embedding text",
        "description": "also should not appear in embedding text",
        "start_datetime": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "end_datetime": datetime(2026, 12, 31, tzinfo=timezone.utc),
        "yes_outcome": "Passes",
        "no_outcome": "Fails",
        "yes_ask_price": 0.4,
        "yes_ask_size": 10.0,
        "yes_bid_price": 0.35,
        "yes_bid_size": 20.0,
        "volume": 100.0,
        "volume_24hr": 10.0,
        "open_interest": 50.0,
    }
    values.update(overrides)
    return Market.model_validate(values)


def test_embedding_text_renders_event_title_and_outcomes() -> None:
    market = _market()

    text = market_embedding_text(market)

    assert text == "Will the bill pass?\nYes: Passes\nNo: Fails"
    assert market.question not in text
    assert market.description not in text
