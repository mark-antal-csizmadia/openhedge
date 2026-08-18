from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from json import loads
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from openhedge_core.api_client import OpenhedgeApiClient, OpenhedgeApiError
from openhedge_core.server import MarketListParams, MarketPage, MarketSearchParams, ReadyStatus, VocabListParams
from openhedge_core.types.market import Event, Market, MarketSource


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
        "yes_ask_size": 10.0,
        "yes_bid_price": 0.35,
        "yes_bid_size": 20.0,
        "volume": 100.0,
        "volume_24hr": 10.0,
        "open_interest": 50.0,
    }
    values.update(overrides)
    return Market.model_validate(values)


@asynccontextmanager
async def api_client(
    handler: Any,
) -> AsyncIterator[OpenhedgeApiClient]:
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as http:
        yield OpenhedgeApiClient(http)


@pytest.mark.asyncio
async def test_ready_parses_status() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"status": "ok", "qdrant": "ok", "embedder": "unconfigured"})

    async with api_client(handler) as client:
        result = await client.ready()

    assert captured["path"] == "/ready"
    assert result == ReadyStatus(status="ok", qdrant="ok", embedder="unconfigured")


@pytest.mark.asyncio
async def test_ready_503_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "not ready"})

    async with api_client(handler) as client:
        with pytest.raises(OpenhedgeApiError) as exc_info:
            await client.ready()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "not ready"


@pytest.mark.asyncio
async def test_browse_markets_encodes_filters_and_parses_page() -> None:
    market = _market(ticker="MKT-1")
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = request.url.query.decode()
        page = MarketPage(
            items=[market],
            next_cursor="next-page",
            limit=5,
        )
        return httpx.Response(200, json=page.model_dump(mode="json"))

    async with api_client(handler) as client:
        result = await client.browse_markets(
            MarketListParams(
                category=["Politics"], yes_ask_price_gte=0.2, yes_ask_price_lte=0.8, limit=5, cursor="abc"
            ),
        )

    assert captured["path"] == "/v1/markets"
    query = parse_qs(captured["query"])
    assert query["category"] == ["Politics"]
    assert query["yes_ask_price_gte"] == ["0.2"]
    assert query["yes_ask_price_lte"] == ["0.8"]
    assert query["limit"] == ["5"]
    assert query["cursor"] == ["abc"]
    assert result.next_cursor == "next-page"
    assert result.limit == 5
    assert result.items[0].ticker == "MKT-1"
    assert "description" not in result.items[0].model_dump()


@pytest.mark.asyncio
async def test_search_markets_sends_query() -> None:
    market = _market(ticker="MKT-0")
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = request.content.decode()
        page = MarketPage(items=[market], next_cursor=None, limit=2)
        return httpx.Response(200, json=page.model_dump(mode="json"))

    async with api_client(handler) as client:
        result = await client.search_markets(MarketSearchParams(q="oil prices", limit=2, tags=["fed"]))

    assert captured["path"] == "/v1/search"
    assert captured["method"] == "POST"
    body = loads(captured["body"])
    assert body["q"] == "oil prices"
    assert body["limit"] == 2
    assert body["tags"] == ["fed"]
    assert result.items[0].ticker == "MKT-0"
    assert result.next_cursor is None
    assert "description" not in result.items[0].model_dump()


@pytest.mark.asyncio
async def test_get_market_parses_payload() -> None:
    market = _market(ticker="MKT-1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/markets/MKT-1"
        return httpx.Response(200, json=market.model_dump(mode="json"))

    async with api_client(handler) as client:
        result = await client.get_market("MKT-1")

    assert result.ticker == "MKT-1"
    assert result.description == "primary secondary"


@pytest.mark.asyncio
async def test_get_event_parses_payload() -> None:
    markets = [
        _market(ticker="MKT-0", strike_order=0),
        _market(ticker="MKT-1", strike_order=1),
    ]
    event = Event.from_markets(markets)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/events/EVT-OPEN"
        return httpx.Response(200, json=event.model_dump(mode="json"))

    async with api_client(handler) as client:
        result = await client.get_event("EVT-OPEN")

    assert result.event_ticker == "EVT-OPEN"
    assert [market.ticker for market in result.markets] == ["MKT-0", "MKT-1"]
    assert result.truncated is False
    assert result.market_count == 2
    assert "description" not in result.markets[0].model_dump()


@pytest.mark.asyncio
async def test_get_market_404_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "market not found"})

    async with api_client(handler) as client:
        with pytest.raises(OpenhedgeApiError) as exc_info:
            await client.get_market("MISSING")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "market not found"


@pytest.mark.asyncio
async def test_search_503_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "search is unavailable: embeddings are not configured"})

    async with api_client(handler) as client:
        with pytest.raises(OpenhedgeApiError) as exc_info:
            await client.search_markets(MarketSearchParams(q="oil"))

    assert exc_info.value.status_code == 503
    assert "embeddings" in exc_info.value.detail


@pytest.mark.asyncio
async def test_list_categories_encodes_limit_and_parses() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = request.url.query.decode()
        return httpx.Response(
            200,
            json={"items": ["Politics", "Economics"], "truncated": False, "limit": 20},
        )

    async with api_client(handler) as client:
        result = await client.list_categories(VocabListParams())

    assert captured["path"] == "/v1/categories"
    query = parse_qs(captured["query"])
    assert query["limit"] == ["20"]
    assert result.items == ["Politics", "Economics"]
    assert result.truncated is False
    assert result.limit == 20


@pytest.mark.asyncio
async def test_list_tags_encodes_limit_and_parses() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = request.url.query.decode()
        return httpx.Response(
            200,
            json={"items": ["elections", "fed"], "truncated": True, "limit": 2},
        )

    async with api_client(handler) as client:
        result = await client.list_tags(VocabListParams(limit=2))

    assert captured["path"] == "/v1/tags"
    query = parse_qs(captured["query"])
    assert "q" not in query
    assert query["limit"] == ["2"]
    assert result.items == ["elections", "fed"]
    assert result.truncated is True
    assert result.limit == 2
