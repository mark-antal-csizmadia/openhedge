from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from openhedge_core.server import EVENT_SCROLL_PAGE_SIZE, MAX_SEARCH_OFFSET, create_app
from openhedge_core.types.market import Market, MarketSource
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
        "outcome_yes": "Yes",
        "outcome_no": "No",
        "price_yes": 0.4,
        "price_no": 0.6,
    }
    values.update(overrides)
    return Market.model_validate(values)


class FakeSearchStore:
    def __init__(self) -> None:
        self.scroll_calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []
        self.get_payload_calls: list[str] = []
        self.scroll_result: tuple[list[dict[str, Any]], str | None] = ([], None)
        self.query_result: list[tuple[dict[str, Any], float]] = []
        self.payloads: dict[str, dict[str, Any]] = {}

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
        self, filters: Filter | None, *, limit: int, cursor: str | None
    ) -> tuple[list[dict[str, Any]], str | None]:
        self.scroll_calls.append({"filters": filters, "limit": limit, "cursor": cursor})
        return self.scroll_result

    async def query_points(
        self, vector: Sequence[float], filters: Filter | None, *, limit: int, offset: int
    ) -> list[tuple[dict[str, Any], float]]:
        self.query_calls.append({"vector": list(vector), "filters": filters, "limit": limit, "offset": offset})
        return list(self.query_result)

    async def get_payload(self, ticker: str) -> dict[str, Any] | None:
        self.get_payload_calls.append(ticker)
        return self.payloads.get(ticker)


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
            params={"category": "Politics", "price_yes_gte": 0.2, "price_yes_lte": 0.8, "limit": 5, "cursor": "abc"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert body["next_cursor"] == "next-page"
    assert body["items"][0]["market"]["ticker"] == "MKT-1"
    assert body["items"][0]["score"] is None
    assert len(store.scroll_calls) == 1
    call = store.scroll_calls[0]
    assert call["limit"] == 5
    assert call["cursor"] == "abc"
    conditions = [condition for condition in (call["filters"].must or []) if isinstance(condition, FieldCondition)]
    by_key = {condition.key: condition for condition in conditions}
    assert by_key["category"].match == MatchValue(value="Politics")
    assert by_key["price_yes"].range == Range(gte=0.2, lte=0.8)


@pytest.mark.asyncio
async def test_search_embeds_query_and_paginates() -> None:
    store = FakeSearchStore()
    embedder = RecordingEmbedder([1.0, 0.0, 0.0])
    markets = [_market(ticker=f"MKT-{i}") for i in range(3)]
    store.query_result = [(market.payload(), 0.9 - i * 0.1) for i, market in enumerate(markets)]
    async with api_client(store, embedder) as client:
        response = await client.get("/search", params={"q": "oil prices", "limit": 2, "tags": "fed"})
    assert response.status_code == 200
    body = response.json()
    assert embedder.calls == [["oil prices"]]
    assert body["limit"] == 2
    assert body["next_cursor"] == "2"
    assert [item["market"]["ticker"] for item in body["items"]] == ["MKT-0", "MKT-1"]
    assert body["items"][0]["score"] == pytest.approx(0.9)
    assert len(store.query_calls) == 1
    call = store.query_calls[0]
    assert call["vector"] == [1.0, 0.0, 0.0]
    assert call["limit"] == 3
    assert call["offset"] == 0
    conditions = [condition for condition in (call["filters"].must or []) if isinstance(condition, FieldCondition)]
    assert conditions[0].key == "tags"
    assert conditions[0].match == MatchValue(value="fed")


@pytest.mark.asyncio
async def test_search_uses_cursor_offset() -> None:
    store = FakeSearchStore()
    store.query_result = [(_market(ticker="MKT-2").payload(), 0.5)]
    async with api_client(store, RecordingEmbedder()) as client:
        response = await client.get("/search", params={"q": "rates", "limit": 2, "cursor": "2"})
    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] is None
    assert store.query_calls[0]["offset"] == 2
    assert store.query_calls[0]["limit"] == 3


@pytest.mark.asyncio
async def test_search_requires_query() -> None:
    async with api_client(FakeSearchStore(), RecordingEmbedder()) as client:
        missing = await client.get("/search")
        empty = await client.get("/search", params={"q": ""})
    assert missing.status_code == 422
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_search_without_embedder_returns_503() -> None:
    async with api_client(FakeSearchStore()) as client:
        response = await client.get("/search", params={"q": "oil"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_search_rejects_invalid_and_oversized_cursors() -> None:
    async with api_client(FakeSearchStore(), RecordingEmbedder()) as client:
        invalid = await client.get("/search", params={"q": "oil", "cursor": "abc"})
        oversized = await client.get(
            "/search",
            params={"q": "oil", "cursor": str(MAX_SEARCH_OFFSET), "limit": 1},
        )
    assert invalid.status_code == 400
    assert oversized.status_code == 400


@pytest.mark.asyncio
async def test_get_market_by_ticker() -> None:
    store = FakeSearchStore()
    market = _market(ticker="MKT-1")
    store.payloads["MKT-1"] = market.payload()
    async with api_client(store) as client:
        response = await client.get("/markets/MKT-1")
    assert response.status_code == 200
    assert response.json()["ticker"] == "MKT-1"
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
    assert len(store.scroll_calls) == 1
    call = store.scroll_calls[0]
    assert call["limit"] == EVENT_SCROLL_PAGE_SIZE
    conditions = [condition for condition in (call["filters"].must or []) if isinstance(condition, FieldCondition)]
    assert conditions[0].key == "event_ticker"
    assert conditions[0].match == MatchValue(value="EVT-OPEN")


@pytest.mark.asyncio
async def test_get_event_missing_returns_404() -> None:
    async with api_client(FakeSearchStore()) as client:
        response = await client.get("/events/MISSING")
    assert response.status_code == 404
