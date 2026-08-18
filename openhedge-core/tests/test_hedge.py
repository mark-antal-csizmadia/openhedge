from datetime import datetime, timezone
from typing import Any

import pytest
from openhedge_core.hedge import HedgeLeg, HedgeParams, size_hedge, size_hedges
from openhedge_core.types.market import Market, MarketSource


def _market(*, ticker: str, **overrides: Any) -> Market:
    values: dict[str, Any] = {
        "source": MarketSource.KALSHI,
        "ticker": ticker,
        "event_ticker": "EVT-OPEN",
        "event_title": "Open event",
        "series_ticker": "SERIES",
        "strike_order": 0,
        "url": f"https://kalshi.com/markets/SERIES/EVT-OPEN?op_market_ticker={ticker}",
        "category": "Politics",
        "tags": ["elections"],
        "question": "Active market",
        "description": "primary secondary",
        "start_datetime": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "end_datetime": datetime(2026, 12, 31, tzinfo=timezone.utc),
        "yes_outcome": "Yes",
        "no_outcome": "No",
        "yes_ask_price": 0.4,
        "yes_ask_size": 1000.0,
        "yes_bid_price": 0.35,
        "yes_bid_size": 20.0,
        "volume": 100.0,
        "volume_24hr": 10.0,
        "open_interest": 50.0,
    }
    values.update(overrides)
    return Market.model_validate(values)


def test_size_hedge_yes_full_coverage() -> None:
    market = _market(ticker="MKT-1")
    candidate = size_hedge(
        market,
        estimated_hit_dollars=100.0,
        coverage=1.0,
        side="yes",
    )
    assert candidate.side == "yes"
    assert candidate.price_per_contract == pytest.approx(0.4)
    assert candidate.available_size == pytest.approx(1000.0)
    assert candidate.contracts == pytest.approx(100.0)
    assert candidate.premium_dollars == pytest.approx(40.0)
    assert candidate.gross_payout_dollars == pytest.approx(100.0)
    assert candidate.net_if_pays == pytest.approx(-40.0)
    assert candidate.net_if_expires == pytest.approx(-40.0)
    assert candidate.liquidity_constrained is False


def test_size_hedge_applies_coverage() -> None:
    market = _market(ticker="MKT-1")
    candidate = size_hedge(
        market,
        estimated_hit_dollars=100.0,
        coverage=0.9,
        side="yes",
    )
    assert candidate.contracts == pytest.approx(90.0)
    assert candidate.premium_dollars == pytest.approx(36.0)
    assert candidate.gross_payout_dollars == pytest.approx(90.0)
    assert candidate.net_if_pays == pytest.approx(-26.0)
    assert candidate.net_if_expires == pytest.approx(-36.0)


def test_size_hedge_caps_at_available_size() -> None:
    market = _market(ticker="MKT-1", yes_ask_size=10.0)
    candidate = size_hedge(
        market,
        estimated_hit_dollars=100.0,
        coverage=1.0,
        side="yes",
    )
    assert candidate.contracts == pytest.approx(10.0)
    assert candidate.premium_dollars == pytest.approx(4.0)
    assert candidate.gross_payout_dollars == pytest.approx(10.0)
    assert candidate.net_if_pays == pytest.approx(86.0)
    assert candidate.liquidity_constrained is True


def test_size_hedge_no_side_uses_complement_ask() -> None:
    market = _market(ticker="MKT-1")
    candidate = size_hedge(
        market,
        estimated_hit_dollars=10.0,
        coverage=1.0,
        side="no",
    )
    assert candidate.side == "no"
    assert candidate.price_per_contract == pytest.approx(0.65)
    assert candidate.available_size == pytest.approx(20.0)
    assert candidate.contracts == pytest.approx(10.0)
    assert candidate.premium_dollars == pytest.approx(6.5)
    assert candidate.gross_payout_dollars == pytest.approx(10.0)
    assert candidate.net_if_pays == pytest.approx(-6.5)
    assert candidate.net_if_expires == pytest.approx(-6.5)
    assert candidate.liquidity_constrained is False


def test_size_hedge_without_hit_is_unit_economics() -> None:
    market = _market(ticker="MKT-1")
    candidate = size_hedge(
        market,
        estimated_hit_dollars=None,
        coverage=1.0,
        side="yes",
    )
    assert candidate.contracts == pytest.approx(1.0)
    assert candidate.premium_dollars == pytest.approx(0.4)
    assert candidate.gross_payout_dollars == pytest.approx(1.0)
    assert candidate.net_if_pays is None
    assert candidate.net_if_expires is None
    assert candidate.liquidity_constrained is False


def test_size_hedges_mixed_sides() -> None:
    yes_market = _market(ticker="MKT-0")
    no_market = _market(ticker="MKT-1", yes_ask_price=0.2, yes_bid_size=1000.0)
    params = HedgeParams(
        legs=[HedgeLeg(ticker="MKT-0", side="yes"), HedgeLeg(ticker="MKT-1", side="no")],
        estimated_hit_dollars=50.0,
        coverage=1.0,
    )
    result = size_hedges([(yes_market, "yes"), (no_market, "no")], params)
    assert result.estimated_hit_dollars == pytest.approx(50.0)
    assert result.coverage == pytest.approx(1.0)
    assert [candidate.market.ticker for candidate in result.candidates] == ["MKT-0", "MKT-1"]
    assert result.candidates[0].side == "yes"
    assert result.candidates[0].premium_dollars == pytest.approx(20.0)
    assert result.candidates[1].side == "no"
    assert result.candidates[1].price_per_contract == pytest.approx(0.65)
    assert result.candidates[1].premium_dollars == pytest.approx(32.5)
