from datetime import datetime, timezone

from openhedge_core.types.market import Market, MarketSource


def test_payload_keeps_deci_cent_prices_and_two_dp_counts() -> None:
    market = Market.model_validate(
        {
            "source": MarketSource.KALSHI,
            "ticker": "KXGOVFLNOMR-26-JFIS",
            "event_ticker": "KXGOVFLNOMR-26",
            "event_title": "Florida GOP nominee",
            "series_ticker": "KXGOVFLNOMR",
            "strike_order": 0,
            "url": "https://kalshi.com/markets/KXGOVFLNOMR/KXGOVFLNOMR-26?op_market_ticker=KXGOVFLNOMR-26-JFIS",
            "category": "Politics",
            "tags": ["elections"],
            "question": "James Fishback",
            "description": "If James Fishback wins the nomination.",
            "start_datetime": datetime(2025, 11, 11, tzinfo=timezone.utc),
            "end_datetime": datetime(2026, 11, 3, 15, tzinfo=timezone.utc),
            "yes_outcome": "James Fishback",
            "no_outcome": "James Fishback",
            "yes_ask_price": 0.013,
            "yes_ask_size": 429905.49,
            "yes_bid_price": 0.012,
            "yes_bid_size": 13281.10,
            "volume": 35219704.85,
            "volume_24hr": 9817011.50,
            "open_interest": 27338803.67,
        }
    )
    payload = market.payload()
    assert payload["yes_ask_price"] == 0.013
    assert payload["yes_bid_price"] == 0.012
    assert payload["yes_ask_size"] == 429905.49
    assert payload["yes_bid_size"] == 13281.1
