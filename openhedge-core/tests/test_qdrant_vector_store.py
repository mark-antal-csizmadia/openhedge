from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from openhedge_core.filters import MarketFilters, to_qdrant_filter
from openhedge_core.vector_store import PayloadUpdate, QdrantVectorStore, VectorPoint, point_id
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

TEST_EMBEDDING_DIM = 8
COLLECTION = "markets"


def _client(*, exists: bool = False, payload_schema: dict[str, SimpleNamespace] | None = None) -> AsyncMock:
    client = AsyncMock()
    client.collection_exists.return_value = exists
    client.get_collection.return_value = SimpleNamespace(payload_schema=payload_schema or {})
    return client


@asynccontextmanager
async def qdrant_store() -> AsyncIterator[tuple[AsyncQdrantClient, QdrantVectorStore]]:
    client = AsyncQdrantClient(location=":memory:")
    store = QdrantVectorStore(client, collection=COLLECTION)
    await store.setup(vector_size=TEST_EMBEDDING_DIM)
    try:
        yield client, store
    finally:
        await client.close()


async def _retrieve(
    client: AsyncQdrantClient,
    ticker: str,
    *,
    with_vectors: bool = False,
) -> Any:
    records = await client.retrieve(
        collection_name=COLLECTION,
        ids=[point_id(ticker)],
        with_payload=True,
        with_vectors=with_vectors,
    )
    assert records
    return records[0]


def _vector(record: Any) -> list[float]:
    vector = record.vector
    if isinstance(vector, dict):
        vector = next(iter(vector.values()))
    return cast(list[float], list(vector))


@pytest.mark.asyncio
async def test_upsert_then_existing_ids() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [
                VectorPoint(
                    id="MKT-NEW",
                    vector=[0.0] * TEST_EMBEDDING_DIM,
                    payload={"ticker": "MKT-NEW", "question": "new"},
                )
            ]
        )

        existing = await store.get_existing_ids(["MKT-NEW", "MKT-MISSING"])
        assert existing == {"MKT-NEW"}


@pytest.mark.asyncio
async def test_update_payloads_merges_without_changing_vector() -> None:
    async with qdrant_store() as (client, store):
        vector = [1.0] * TEST_EMBEDDING_DIM
        await store.upsert_points(
            [
                VectorPoint(
                    id="MKT-EXISTING",
                    vector=vector,
                    payload={"question": "old", "yes_ask_price": 0.1, "yes_outcome": "Yes"},
                )
            ]
        )
        stored_vector = _vector(await _retrieve(client, "MKT-EXISTING", with_vectors=True))

        await store.update_payloads(
            [PayloadUpdate(id="MKT-EXISTING", payload={"yes_ask_price": 0.7, "question": "updated"})]
        )

        record = await _retrieve(client, "MKT-EXISTING", with_vectors=True)
        assert _vector(record) == stored_vector
        assert record.payload["yes_ask_price"] == 0.7
        assert record.payload["question"] == "updated"
        assert record.payload["yes_outcome"] == "Yes"


@pytest.mark.asyncio
async def test_delete_points() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [
                VectorPoint(id="MKT-CLOSED", vector=[0.0] * TEST_EMBEDDING_DIM, payload={}),
                VectorPoint(id="KEEP", vector=[0.0] * TEST_EMBEDDING_DIM, payload={}),
            ]
        )

        await store.delete_points(["MKT-CLOSED"])

        existing = await store.get_existing_ids(["MKT-CLOSED", "KEEP"])
        assert existing == {"KEEP"}


@pytest.mark.asyncio
async def test_missing_ids_are_noop() -> None:
    async with qdrant_store() as (_, store):
        await store.update_payloads([PayloadUpdate(id="MISSING", payload={"yes_ask_price": 0.5})])
        await store.delete_points(["MISSING"])
        assert await store.get_existing_ids(["MISSING"]) == set()


@pytest.mark.asyncio
async def test_setup_creates_collection_when_missing() -> None:
    client = _client(exists=False)
    store = QdrantVectorStore(client, collection=COLLECTION)

    await store.setup(vector_size=TEST_EMBEDDING_DIM)

    client.create_collection.assert_awaited_once_with(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=TEST_EMBEDDING_DIM, distance=Distance.COSINE),
    )


@pytest.mark.asyncio
async def test_setup_is_idempotent() -> None:
    existing = {
        field_name: SimpleNamespace(data_type=schema)
        for field_name, schema in QdrantVectorStore.PAYLOAD_INDEXES.items()
    }
    client = _client(exists=True, payload_schema=existing)
    store = QdrantVectorStore(client, collection=COLLECTION)

    await store.setup(vector_size=TEST_EMBEDDING_DIM)
    await store.setup(vector_size=TEST_EMBEDDING_DIM)

    client.create_collection.assert_not_awaited()
    client.create_payload_index.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_creates_missing_payload_indexes() -> None:
    client = _client(exists=True)
    store = QdrantVectorStore(client, collection=COLLECTION)

    await store.setup(vector_size=TEST_EMBEDDING_DIM)

    created = {
        call.kwargs["field_name"]: call.kwargs["field_schema"] for call in client.create_payload_index.await_args_list
    }
    assert created == QdrantVectorStore.PAYLOAD_INDEXES
    for call in client.create_payload_index.await_args_list:
        assert call.kwargs["collection_name"] == COLLECTION


def _dense(index: int) -> list[float]:
    vector = [0.0] * TEST_EMBEDDING_DIM
    vector[index] = 1.0
    return vector


@pytest.mark.asyncio
async def test_scroll_pages_do_not_overlap() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [VectorPoint(id=f"MKT-{i}", vector=_dense(0), payload={"ticker": f"MKT-{i}"}) for i in range(5)]
        )

        page1, cursor1 = await store.scroll_points(None, limit=2, cursor=None)
        page2, cursor2 = await store.scroll_points(None, limit=2, cursor=cursor1)
        page3, cursor3 = await store.scroll_points(None, limit=2, cursor=cursor2)

        tickers1 = {payload["ticker"] for payload in page1}
        tickers2 = {payload["ticker"] for payload in page2}
        tickers3 = {payload["ticker"] for payload in page3}
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1
        assert tickers1.isdisjoint(tickers2)
        assert tickers1.isdisjoint(tickers3)
        assert tickers2.isdisjoint(tickers3)
        assert cursor1 is not None
        assert cursor2 is not None
        assert cursor3 is None


@pytest.mark.asyncio
async def test_scroll_applies_payload_filter() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [
                VectorPoint(id="POL", vector=_dense(0), payload={"ticker": "POL", "category": "Politics"}),
                VectorPoint(id="SPT", vector=_dense(1), payload={"ticker": "SPT", "category": "Sports"}),
            ]
        )
        payloads, next_cursor = await store.scroll_points(
            to_qdrant_filter(MarketFilters(category=["Sports"])),
            limit=10,
            cursor=None,
        )
        assert [payload["ticker"] for payload in payloads] == ["SPT"]
        assert next_cursor is None


@pytest.mark.asyncio
async def test_query_returns_nearest_neighbors_with_filters() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [
                VectorPoint(id="NEAR", vector=_dense(0), payload={"ticker": "NEAR", "category": "Politics"}),
                VectorPoint(id="FAR", vector=_dense(1), payload={"ticker": "FAR", "category": "Sports"}),
            ]
        )

        payloads = await store.query_points(_dense(0), None, limit=2)
        assert [payload["ticker"] for payload in payloads] == ["NEAR", "FAR"]

        filtered = await store.query_points(
            _dense(0),
            to_qdrant_filter(MarketFilters(category=["Sports"])),
            limit=2,
        )
        assert [payload["ticker"] for payload in filtered] == ["FAR"]


@pytest.mark.asyncio
async def test_get_payload_returns_payload_or_none() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [
                VectorPoint(
                    id="MKT-NEW",
                    vector=[0.0] * TEST_EMBEDDING_DIM,
                    payload={"ticker": "MKT-NEW", "question": "new"},
                )
            ]
        )

        assert await store.get_payload("MKT-NEW") == {"ticker": "MKT-NEW", "question": "new"}
        assert await store.get_payload("MISSING") is None


@pytest.mark.asyncio
async def test_scroll_and_query_honor_payload_field_mask() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [
                VectorPoint(
                    id="MKT-NEW",
                    vector=_dense(0),
                    payload={
                        "ticker": "MKT-NEW",
                        "question": "new",
                        "description": "long rules text",
                        "volume": 100.0,
                    },
                )
            ]
        )

        payloads, _ = await store.scroll_points(
            None,
            limit=10,
            cursor=None,
            payload_fields=["ticker", "question"],
        )
        assert payloads == [{"ticker": "MKT-NEW", "question": "new"}]

        payloads = await store.query_points(
            _dense(0),
            None,
            limit=1,
            payload_fields=["ticker"],
        )
        assert payloads == [{"ticker": "MKT-NEW"}]


@pytest.mark.asyncio
async def test_facet_values_returns_unique_categories() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [
                VectorPoint(id="POL-1", vector=_dense(0), payload={"category": "Politics"}),
                VectorPoint(id="POL-2", vector=_dense(1), payload={"category": "Politics"}),
                VectorPoint(id="SPT", vector=_dense(2), payload={"category": "Sports"}),
            ]
        )

        values = await store.facet_values("category", limit=10)
        assert values == ["Politics", "Sports"]


@pytest.mark.asyncio
async def test_facet_values_explodes_tag_arrays_and_honors_limit() -> None:
    async with qdrant_store() as (_, store):
        await store.upsert_points(
            [
                VectorPoint(id="A", vector=_dense(0), payload={"tags": ["elections", "fed"]}),
                VectorPoint(id="B", vector=_dense(1), payload={"tags": ["elections"]}),
                VectorPoint(id="C", vector=_dense(2), payload={"tags": ["nba"]}),
            ]
        )

        values = await store.facet_values("tags", limit=10)
        assert values[0] == "elections"
        assert set(values) == {"elections", "fed", "nba"}
        assert await store.facet_values("tags", limit=1) == ["elections"]
