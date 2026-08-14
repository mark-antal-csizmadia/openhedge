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
        "outcome_yes": "Passes",
        "outcome_no": "Fails",
        "price_yes": 0.4,
        "price_no": 0.6,
    }
    values.update(overrides)
    return Market.model_validate(values)


def test_embedding_text_renders_event_title_and_outcomes() -> None:
    market = _market()

    text = market_embedding_text(market)

    assert text == "Will the bill pass?\nYes: Passes\nNo: Fails"
    assert market.question not in text
    assert market.description not in text
