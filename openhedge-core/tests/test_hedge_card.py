from datetime import datetime, timezone
from typing import Any

import pytest
from openhedge_core.hedge import HedgeCardParams, HedgeParams, compose_hedge_card, size_hedge
from openhedge_core.types.market import Market, MarketSource
from pydantic import ValidationError


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
        "question": "WTI above $135",
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


def test_compose_hedge_card_fit_unconstrained() -> None:
    candidate = size_hedge(
        _market(ticker="MKT-1"),
        HedgeParams(ticker="MKT-1", estimated_hit_dollars=100.0, coverage=1.0, side="yes"),
    )
    card = compose_hedge_card(
        HedgeCardParams(
            verdict="fit",
            headline="Diesel above $5 could cost this business $100.",
            basis_risk="The closest market follows crude rather than diesel.",
            candidate=candidate,
        )
    )
    assert card.verdict == "fit"
    assert card.candidate is not None
    assert card.candidate.premium_dollars == pytest.approx(40.0)
    markdown = card.markdown
    assert markdown.startswith("## Diesel above $5 could cost this business $100.")
    assert "The closest market follows crude rather than diesel." in markdown
    assert "You pay up front: $40.00" in markdown
    assert "Estimated hit: $100.00" in markdown
    assert "Market pays gross: $100.00" in markdown
    assert "WTI above $135 (YES)" in markdown
    assert "Net: -$40.00" in markdown
    assert "Open this market: https://kalshi.com/markets/SERIES/EVT-OPEN?op_market_ticker=MKT-1" in markdown
    assert "Liquidity constrained" not in markdown
    assert "No current market fits" not in markdown
    assert "### Other exposures" not in markdown


def test_compose_hedge_card_fit_liquidity_constrained() -> None:
    candidate = size_hedge(
        _market(ticker="MKT-1", yes_ask_size=10.0),
        HedgeParams(ticker="MKT-1", estimated_hit_dollars=100.0, coverage=1.0, side="yes"),
    )
    card = compose_hedge_card(
        HedgeCardParams(
            verdict="fit",
            headline="Diesel spike.",
            basis_risk="Crude is a proxy.",
            candidate=candidate,
        )
    )
    markdown = card.markdown
    assert "You pay up front: $4.00" in markdown
    assert "Market pays gross: $10.00" in markdown
    assert "Net: $86.00" in markdown
    assert "Liquidity constrained:" in markdown
    assert "wanted 100.00 contracts ($100.00)" in markdown
    assert "book quoted 10.00" in markdown
    assert "Filled 10.00 contracts ($10.00 gross)" in markdown
    assert "coverage achieved 0.1 of estimated hit" in markdown


def test_compose_hedge_card_unit_economics_omits_hit_worlds() -> None:
    candidate = size_hedge(_market(ticker="MKT-1"), HedgeParams(ticker="MKT-1", side="yes"))
    card = compose_hedge_card(
        HedgeCardParams(
            verdict="fit",
            headline="Unit hedge.",
            basis_risk="No dollar hit was given.",
            candidate=candidate,
        )
    )
    markdown = card.markdown
    assert "You pay up front: $0.40" in markdown
    assert "Market pays gross: $1.00 (unit $1.00 payout)" in markdown
    assert "Estimated hit:" not in markdown
    assert "### Event happens" not in markdown
    assert "### Event does not" not in markdown
    assert "Liquidity constrained" not in markdown


def test_compose_hedge_card_none_omits_dollars() -> None:
    card = compose_hedge_card(
        HedgeCardParams(
            verdict="none",
            headline="No cruise-weekend contract.",
            basis_risk="No listed market covers this shop's weekend sales.",
        )
    )
    assert card.candidate is None
    markdown = card.markdown
    assert "No cruise-weekend contract." in markdown
    assert "No current market fits this exposure." in markdown
    assert "You pay up front" not in markdown
    assert "Estimated hit" not in markdown
    assert "Open this market" not in markdown
    assert "$" not in markdown


def test_compose_hedge_card_includes_other_exposures() -> None:
    card = compose_hedge_card(
        HedgeCardParams(
            verdict="none",
            headline="Headline",
            basis_risk="None maps.",
            other_exposures=["Freight demand", "Equipment financing"],
        )
    )
    assert "### Other exposures" in card.markdown
    assert "- Freight demand" in card.markdown
    assert "- Equipment financing" in card.markdown


def test_hedge_card_params_fit_requires_candidate() -> None:
    with pytest.raises(ValidationError, match="verdict=fit requires candidate"):
        HedgeCardParams(verdict="fit", headline="Headline", basis_risk="Basis")


def test_hedge_card_params_none_rejects_candidate() -> None:
    candidate = size_hedge(
        _market(ticker="MKT-1"),
        HedgeParams(ticker="MKT-1", estimated_hit_dollars=100.0, side="yes"),
    )
    with pytest.raises(ValidationError, match="verdict=none rejects candidate"):
        HedgeCardParams(verdict="none", headline="Headline", basis_risk="Basis", candidate=candidate)
