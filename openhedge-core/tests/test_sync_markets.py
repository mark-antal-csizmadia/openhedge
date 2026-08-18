import asyncio
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
import pytest
from aiolimiter import AsyncLimiter
from openhedge_core.apis.kalshi import EVENTS_URL, SERIES_URL
from openhedge_core.consumer import Consumer
from openhedge_core.embeddings import market_embedding_text
from openhedge_core.producer import Producer
from openhedge_core.sync_markets import consume_closed_batch, consume_open_batch, run
from openhedge_core.types.kalshi import KalshiEvent, KalshiMarket, KalshiSeries
from openhedge_core.types.market import Market, MarketSource
from openhedge_core.vector_store import PayloadUpdate, VectorPoint
from qdrant_client.models import Filter

TEST_EMBEDDING_DIM = 8

MARKET_ACTIVE = {
    "ticker": "MKT-ACTIVE",
    "title": "Active market",
    "rules_primary": "primary",
    "rules_secondary": "secondary",
    "open_time": "2024-01-01T00:00:00Z",
    "close_time": "2024-12-31T00:00:00Z",
    "yes_sub_title": "Yes",
    "no_sub_title": "No",
    "status": "active",
    "last_price_dollars": 0.5,
    "yes_ask_dollars": 0.55,
    "yes_ask_size_fp": 10.0,
    "yes_bid_dollars": 0.45,
    "yes_bid_size_fp": 20.0,
    "volume_fp": 10.0,
    "volume_24h_fp": 1.0,
    "open_interest_fp": 5.0,
}

MARKET_CLOSED = {
    **MARKET_ACTIVE,
    "ticker": "MKT-CLOSED",
    "title": "Closed market",
    "status": "closed",
}

EVENT_OPEN = {
    "event_ticker": "EVT-OPEN",
    "title": "Open event",
    "series_ticker": "SERIES",
    "markets": [MARKET_ACTIVE, MARKET_CLOSED],
}

EVENT_CLOSED = {
    "event_ticker": "EVT-CLOSED",
    "title": "Closed event",
    "series_ticker": "SERIES",
    "markets": [MARKET_CLOSED],
}

SERIES = {"ticker": "SERIES", "category": "Politics", "tags": ["elections"]}


class FakeVectorStore:
    def __init__(self) -> None:
        self.points: dict[str, VectorPoint] = {}

    async def setup(self, *, vector_size: int) -> None:
        return

    async def get_existing_ids(self, ids: Sequence[str]) -> set[str]:
        return {point_id for point_id in ids if point_id in self.points}

    async def upsert_points(self, points: Sequence[VectorPoint]) -> None:
        for point in points:
            self.points[point.id] = point

    async def update_payloads(self, updates: Sequence[PayloadUpdate]) -> None:
        for update in updates:
            existing = self.points.get(update.id)
            if existing is None:
                continue
            self.points[update.id] = existing.model_copy(update={"payload": {**existing.payload, **update.payload}})

    async def delete_points(self, ids: Sequence[str]) -> None:
        for ticker in ids:
            self.points.pop(ticker, None)

    async def scroll_points(
        self,
        filters: Filter | None,
        *,
        limit: int,
        cursor: str | None,
        payload_fields: Sequence[str] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        raise NotImplementedError

    async def query_points(
        self,
        vector: Sequence[float],
        filters: Filter | None,
        *,
        limit: int,
        payload_fields: Sequence[str] | None = None,
    ) -> list[tuple[dict[str, Any], float]]:
        raise NotImplementedError

    async def get_payload(self, ticker: str) -> dict[str, Any] | None:
        point = self.points.get(ticker)
        if point is None:
            return None
        return point.payload

    async def facet_values(self, field: Literal["category", "tags"], *, limit: int) -> list[str]:
        raise NotImplementedError


class RecordingEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.0] * TEST_EMBEDDING_DIM for _ in texts]


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


def _json_response(status_code: int, payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


@pytest.fixture
def limiter() -> AsyncLimiter:
    return AsyncLimiter(max_rate=1000, time_period=1)


@pytest.mark.asyncio
async def test_consume_open_batch_embeds_and_upserts_missing() -> None:
    store = FakeVectorStore()
    embedder = RecordingEmbedder()
    market = _market(ticker="MKT-NEW")

    await consume_open_batch([market], embedder=embedder, store=store)

    assert len(embedder.calls) == 1
    assert embedder.calls[0] == [market_embedding_text(market)]
    assert "MKT-NEW" in store.points
    assert store.points["MKT-NEW"].payload["question"] == "Active market"
    assert store.points["MKT-NEW"].payload["yes_outcome"] == "Yes"


@pytest.mark.asyncio
async def test_consume_open_batch_updates_payload_without_embedding() -> None:
    store = FakeVectorStore()
    embedder = RecordingEmbedder()
    market = _market(ticker="MKT-EXISTING", yes_ask_price=0.7, yes_bid_price=0.3)
    store.points["MKT-EXISTING"] = VectorPoint(
        id="MKT-EXISTING",
        vector=[1.0] * TEST_EMBEDDING_DIM,
        payload={"question": "old", "yes_ask_price": 0.1, "yes_outcome": "Yes"},
    )

    await consume_open_batch([market], embedder=embedder, store=store)

    assert embedder.calls == []
    point = store.points["MKT-EXISTING"]
    assert point.vector == [1.0] * TEST_EMBEDDING_DIM
    assert point.payload["yes_ask_price"] == 0.7
    assert point.payload["question"] == "Active market"
    assert point.payload["yes_outcome"] == "Yes"


@pytest.mark.asyncio
async def test_consume_closed_batch_deletes_ids() -> None:
    store = FakeVectorStore()
    store.points["MKT-CLOSED"] = VectorPoint(id="MKT-CLOSED", vector=[0.0], payload={})
    store.points["KEEP"] = VectorPoint(id="KEEP", vector=[0.0], payload={})

    await consume_closed_batch(["MKT-CLOSED"], store=store)

    assert "MKT-CLOSED" not in store.points
    assert "KEEP" in store.points


@pytest.mark.asyncio
async def test_run_syncs_open_and_closed_markets(limiter: AsyncLimiter) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(EVENTS_URL):
            status = request.url.params.get("status")
            if status == "open":
                return _json_response(200, {"events": [EVENT_OPEN], "cursor": None})
            if status == "closed":
                return _json_response(200, {"events": [EVENT_CLOSED], "cursor": None})
            raise AssertionError(f"unexpected status={status!r}")
        if url.startswith(f"{SERIES_URL}/"):
            return _json_response(200, {"series": SERIES})
        raise AssertionError(f"unexpected url={url}")

    store = FakeVectorStore()
    store.points["MKT-ACTIVE"] = VectorPoint(
        id="MKT-ACTIVE",
        vector=[1.0] * TEST_EMBEDDING_DIM,
        payload={"yes_ask_price": 0.1, "yes_outcome": "Yes"},
    )
    store.points["MKT-CLOSED"] = VectorPoint(id="MKT-CLOSED", vector=[0.0], payload={})
    embedder = RecordingEmbedder()

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await run(client=client, limiter=limiter, embedder=embedder, store=store, batch_size=10)

    assert embedder.calls == []
    assert "MKT-ACTIVE" in store.points
    assert store.points["MKT-ACTIVE"].payload["yes_ask_price"] == 0.55
    assert store.points["MKT-ACTIVE"].vector == [1.0] * TEST_EMBEDDING_DIM
    assert "MKT-CLOSED" not in store.points


@pytest.mark.asyncio
async def test_run_embeds_new_open_market(limiter: AsyncLimiter) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(EVENTS_URL):
            status = request.url.params.get("status")
            if status == "open":
                return _json_response(200, {"events": [EVENT_OPEN], "cursor": None})
            if status == "closed":
                return _json_response(200, {"events": [], "cursor": None})
            raise AssertionError(f"unexpected status={status!r}")
        if url.startswith(f"{SERIES_URL}/"):
            return _json_response(200, {"series": SERIES})
        raise AssertionError(f"unexpected url={url}")

    store = FakeVectorStore()
    embedder = RecordingEmbedder()
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await run(client=client, limiter=limiter, embedder=embedder, store=store, batch_size=10)

    assert len(embedder.calls) == 1
    assert "MKT-ACTIVE" in store.points
    assert store.points["MKT-ACTIVE"].vector == [0.0] * TEST_EMBEDDING_DIM


@pytest.mark.asyncio
async def test_from_kalshi_rest_api_uses_series_and_strike_order() -> None:
    event = KalshiEvent.model_validate(EVENT_OPEN)
    market = KalshiMarket.model_validate(MARKET_CLOSED)
    series = KalshiSeries.model_validate(SERIES)
    mapped = Market.from_kalshi_rest_api(event, market, series, strike_order=1)

    assert mapped.strike_order == 1
    assert mapped.category == "Politics"
    assert mapped.tags == ["elections"]
    assert mapped.series_ticker == "SERIES"
    assert mapped.yes_ask_price == 0.55
    assert mapped.yes_bid_price == 0.45


@pytest.mark.asyncio
async def test_producer_reraises() -> None:
    async def produce():
        yield 1
        raise RuntimeError("boom")

    queue: asyncio.Queue[int] = asyncio.Queue()
    producer = Producer(name="test", produce_fn=produce, queue=queue, shutdown_event=asyncio.Event())
    with pytest.raises(RuntimeError, match="boom"):
        await producer.run()


@pytest.mark.asyncio
async def test_consumer_reraises() -> None:
    async def consume(batch: Sequence[str]) -> None:
        raise RuntimeError("boom")

    queue: asyncio.Queue[str] = asyncio.Queue()
    await queue.put("x")
    consumer = Consumer(
        name="test",
        consume_fn=consume,
        queue=queue,
        shutdown_event=asyncio.Event(),
        batch_size=1,
        producers_done=asyncio.Event(),
    )
    with pytest.raises(RuntimeError, match="boom"):
        await consumer.run()
