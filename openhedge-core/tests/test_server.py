from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
import pytest
from openhedge_core.server import (
    DEFAULT_VOCAB_LIMIT,
    EVENT_SCROLL_PAGE_SIZE,
    MAX_EVENT_MARKETS,
    MAX_VOCAB_LIMIT,
    create_app,
)
from openhedge_core.types.market import MARKET_SUMMARY_PAYLOAD_FIELDS, Market, MarketSource
from openhedge_core.vector_store import PayloadUpdate, VectorPoint
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range


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


_FAT_MARKET_FIELDS = {
    "description",
    "tags",
    "start_datetime",
    "volume",
    "volume_24hr",
    "open_interest",
    "updated_datetime",
}


def _assert_compact_market(market: dict[str, Any]) -> None:
    assert market["ticker"]
    assert market["question"]
    assert "yes_ask_size" in market
    assert "yes_bid_size" in market
    assert "strike_order" in market
    for field in _FAT_MARKET_FIELDS:
        assert field not in market


class FakeSearchStore:
    def __init__(self) -> None:
        self.scroll_calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []
        self.get_payload_calls: list[str] = []
        self.scroll_result: tuple[list[dict[str, Any]], str | None] = ([], None)
        self.query_result: list[tuple[dict[str, Any], float]] = []
        self.payloads: dict[str, dict[str, Any]] = {}
        self.facet_calls: list[dict[str, Any]] = []
        self.facet_result: dict[str, list[str]] = {}

    async def setup(self, *, vector_size: int) -> None:
        return

    async def get_existing_ids(self, ids: Sequence[str]) -> set[str]:
        return set()

    async def upsert_points(self, points: Sequence[VectorPoint]) -> None:
        return

    async def update_payloads(self, updates: Sequence[PayloadUpdate]) -> None:
        return

    async def delete_points(self, ids: Sequence[str]) -> None:
        return

    async def scroll_points(
        self,
        filters: Filter | None,
        *,
        limit: int,
        cursor: str | None,
        payload_fields: Sequence[str] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        self.scroll_calls.append(
            {"filters": filters, "limit": limit, "cursor": cursor, "payload_fields": payload_fields}
        )
        return self.scroll_result

    async def query_points(
        self,
        vector: Sequence[float],
        filters: Filter | None,
        *,
        limit: int,
        payload_fields: Sequence[str] | None = None,
    ) -> list[tuple[dict[str, Any], float]]:
        self.query_calls.append(
            {
                "vector": list(vector),
                "filters": filters,
                "limit": limit,
                "payload_fields": payload_fields,
            }
        )
        return list(self.query_result)

    async def get_payload(self, ticker: str) -> dict[str, Any] | None:
        self.get_payload_calls.append(ticker)
        return self.payloads.get(ticker)

    async def facet_values(self, field: Literal["category", "tags"], *, limit: int) -> list[str]:
        self.facet_calls.append({"field": field, "limit": limit})
        return list(self.facet_result.get(field, []))[:limit]


class RecordingEmbedder:
    def __init__(self, vector: list[float] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.vector = vector or [0.1, 0.2, 0.3]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [list(self.vector) for _ in texts]


@asynccontextmanager
async def api_client(
    store: FakeSearchStore,
    embedder: RecordingEmbedder | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(store=store, embedder=embedder)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health() -> None:
    store = FakeSearchStore()
    async with api_client(store) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_browse_returns_page_and_forwards_filters() -> None:
    store = FakeSearchStore()
    market = _market(ticker="MKT-1")
    store.scroll_result = ([market.payload()], "next-page")
    async with api_client(store) as client:
        response = await client.get(
            "/markets",
            params={
                "category": "Politics",
                "yes_ask_price_gte": 0.2,
                "yes_ask_price_lte": 0.8,
                "limit": 5,
                "cursor": "abc",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert body["next_cursor"] == "next-page"
    assert body["items"][0]["market"]["ticker"] == "MKT-1"
    assert body["items"][0]["score"] is None
    _assert_compact_market(body["items"][0]["market"])
    assert len(store.scroll_calls) == 1
    call = store.scroll_calls[0]
    assert call["limit"] == 5
    assert call["cursor"] == "abc"
    assert call["payload_fields"] == MARKET_SUMMARY_PAYLOAD_FIELDS
    conditions = [condition for condition in (call["filters"].must or []) if isinstance(condition, FieldCondition)]
    by_key = {condition.key: condition for condition in conditions}
    assert by_key["category"].match == MatchValue(value="Politics")
    assert by_key["yes_ask_price"].range == Range(gte=0.2, lte=0.8)


@pytest.mark.asyncio
async def test_search_embeds_query_and_returns_neighbors() -> None:
    store = FakeSearchStore()
    embedder = RecordingEmbedder([1.0, 0.0, 0.0])
    markets = [_market(ticker=f"MKT-{i}") for i in range(3)]
    store.query_result = [(market.payload(), 0.9 - i * 0.1) for i, market in enumerate(markets)]
    async with api_client(store, embedder) as client:
        response = await client.post("/search", json={"q": "oil prices", "limit": 2, "tags": ["fed"]})
    assert response.status_code == 200
    body = response.json()
    assert embedder.calls == [["oil prices"]]
    assert body["limit"] == 2
    assert body["next_cursor"] is None
    assert [item["market"]["ticker"] for item in body["items"]] == ["MKT-0", "MKT-1", "MKT-2"]
    assert body["items"][0]["score"] == pytest.approx(0.9)
    _assert_compact_market(body["items"][0]["market"])
    assert len(store.query_calls) == 1
    call = store.query_calls[0]
    assert call["vector"] == [1.0, 0.0, 0.0]
    assert call["limit"] == 2
    assert call["payload_fields"] == MARKET_SUMMARY_PAYLOAD_FIELDS
    conditions = [condition for condition in (call["filters"].must or []) if isinstance(condition, FieldCondition)]
    assert conditions[0].key == "tags"
    assert conditions[0].match == MatchValue(value="fed")


@pytest.mark.asyncio
async def test_search_requires_query() -> None:
    async with api_client(FakeSearchStore(), RecordingEmbedder()) as client:
        missing = await client.post("/search", json={})
        empty = await client.post("/search", json={"q": ""})
    assert missing.status_code == 422
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_search_without_embedder_returns_503() -> None:
    async with api_client(FakeSearchStore()) as client:
        response = await client.post("/search", json={"q": "oil"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_search_rejects_cursor() -> None:
    async with api_client(FakeSearchStore(), RecordingEmbedder()) as client:
        response = await client.post("/search", json={"q": "oil", "cursor": "abc"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_market_by_ticker() -> None:
    store = FakeSearchStore()
    market = _market(ticker="MKT-1")
    store.payloads["MKT-1"] = market.payload()
    async with api_client(store) as client:
        response = await client.get("/markets/MKT-1")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "MKT-1"
    assert body["description"] == "primary secondary"
    assert body["volume"] == pytest.approx(100.0)
    assert body["open_interest"] == pytest.approx(50.0)
    assert store.get_payload_calls == ["MKT-1"]


@pytest.mark.asyncio
async def test_get_market_missing_returns_404() -> None:
    async with api_client(FakeSearchStore()) as client:
        response = await client.get("/markets/MISSING")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_event_orders_markets_by_strike_order() -> None:
    store = FakeSearchStore()
    markets = [
        _market(ticker="MKT-2", strike_order=2, event_ticker="EVT-OPEN"),
        _market(ticker="MKT-0", strike_order=0, event_ticker="EVT-OPEN"),
        _market(ticker="MKT-1", strike_order=1, event_ticker="EVT-OPEN"),
    ]
    store.scroll_result = ([market.payload() for market in markets], None)
    async with api_client(store) as client:
        response = await client.get("/events/EVT-OPEN")
    assert response.status_code == 200
    body = response.json()
    assert body["event_ticker"] == "EVT-OPEN"
    assert body["event_title"] == "Open event"
    assert [market["ticker"] for market in body["markets"]] == ["MKT-0", "MKT-1", "MKT-2"]
    assert [market["strike_order"] for market in body["markets"]] == [0, 1, 2]
    assert body["truncated"] is False
    assert body["market_count"] == 3
    assert "tags" not in body
    for market in body["markets"]:
        _assert_compact_market(market)
    assert len(store.scroll_calls) == 1
    call = store.scroll_calls[0]
    assert call["limit"] == EVENT_SCROLL_PAGE_SIZE
    assert call["payload_fields"] == MARKET_SUMMARY_PAYLOAD_FIELDS
    conditions = [condition for condition in (call["filters"].must or []) if isinstance(condition, FieldCondition)]
    assert conditions[0].key == "event_ticker"
    assert conditions[0].match == MatchValue(value="EVT-OPEN")


@pytest.mark.asyncio
async def test_get_event_caps_markets_and_sets_truncated() -> None:
    store = FakeSearchStore()
    total = MAX_EVENT_MARKETS + 1
    markets = [
        _market(ticker=f"MKT-{strike_order}", strike_order=strike_order, event_ticker="EVT-OPEN")
        for strike_order in range(total - 1, -1, -1)
    ]
    store.scroll_result = ([market.payload() for market in markets], None)
    async with api_client(store) as client:
        response = await client.get("/events/EVT-OPEN")
    assert response.status_code == 200
    body = response.json()
    assert body["truncated"] is True
    assert body["market_count"] == total
    assert [market["ticker"] for market in body["markets"]] == [f"MKT-{i}" for i in range(MAX_EVENT_MARKETS)]
    assert [market["strike_order"] for market in body["markets"]] == list(range(MAX_EVENT_MARKETS))
    for market in body["markets"]:
        _assert_compact_market(market)
    assert store.scroll_calls[0]["limit"] == EVENT_SCROLL_PAGE_SIZE


@pytest.mark.asyncio
async def test_get_event_missing_returns_404() -> None:
    async with api_client(FakeSearchStore()) as client:
        response = await client.get("/events/MISSING")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_categories_returns_popularity_order() -> None:
    store = FakeSearchStore()
    store.facet_result["category"] = ["Sports", "Politics", "Economics"]
    async with api_client(store) as client:
        response = await client.get("/categories")
    assert response.status_code == 200
    assert response.json() == {
        "items": ["Sports", "Politics", "Economics"],
        "truncated": False,
        "limit": DEFAULT_VOCAB_LIMIT,
    }
    assert store.facet_calls == [{"field": "category", "limit": DEFAULT_VOCAB_LIMIT}]


@pytest.mark.asyncio
async def test_list_categories_truncated_when_facet_fills_limit() -> None:
    store = FakeSearchStore()
    store.facet_result["category"] = ["A", "B", "C"]
    async with api_client(store) as client:
        response = await client.get("/categories", params={"limit": 3})
    assert response.status_code == 200
    assert response.json() == {"items": ["A", "B", "C"], "truncated": True, "limit": 3}
    assert store.facet_calls == [{"field": "category", "limit": 3}]


@pytest.mark.asyncio
async def test_list_tags_returns_popular_values() -> None:
    store = FakeSearchStore()
    store.facet_result["tags"] = ["elections", "fed", "federal-reserve", "nba"]
    async with api_client(store) as client:
        response = await client.get("/tags")
    assert response.status_code == 200
    assert response.json() == {
        "items": ["elections", "fed", "federal-reserve", "nba"],
        "truncated": False,
        "limit": DEFAULT_VOCAB_LIMIT,
    }
    assert store.facet_calls == [{"field": "tags", "limit": DEFAULT_VOCAB_LIMIT}]


@pytest.mark.asyncio
async def test_list_tags_honors_limit_and_truncated() -> None:
    store = FakeSearchStore()
    store.facet_result["tags"] = ["elections", "fed", "federal-reserve", "nba"]
    async with api_client(store) as client:
        response = await client.get("/tags", params={"limit": 2})
    assert response.status_code == 200
    assert response.json() == {"items": ["elections", "fed"], "truncated": True, "limit": 2}
    assert store.facet_calls == [{"field": "tags", "limit": 2}]


@pytest.mark.asyncio
async def test_vocab_limit_out_of_range_returns_422() -> None:
    async with api_client(FakeSearchStore()) as client:
        too_low = await client.get("/tags", params={"limit": 0})
        too_high = await client.get("/categories", params={"limit": MAX_VOCAB_LIMIT + 1})
    assert too_low.status_code == 422
    assert too_high.status_code == 422
