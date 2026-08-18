import logging
import uuid
from collections.abc import Sequence
from typing import Any, ClassVar, Literal, Protocol

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    PayloadSchemaType,
    PointStruct,
    SetPayload,
    SetPayloadOperation,
    VectorParams,
)

DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_QDRANT_COLLECTION = "markets"
POINT_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://openhedge.dev/markets")

logger = logging.getLogger(__name__)


def point_id(ticker: str) -> str:
    return str(uuid.uuid5(POINT_ID_NAMESPACE, ticker))


class VectorPoint(BaseModel):
    id: str
    vector: list[float]
    payload: dict[str, Any]


class PayloadUpdate(BaseModel):
    id: str
    payload: dict[str, Any]


class VectorStore(Protocol):
    async def setup(self, *, vector_size: int) -> None: ...

    async def get_existing_ids(self, ids: Sequence[str]) -> set[str]: ...

    async def get_payload(self, ticker: str) -> dict[str, Any] | None: ...

    async def upsert_points(self, points: Sequence[VectorPoint]) -> None: ...

    async def update_payloads(self, updates: Sequence[PayloadUpdate]) -> None: ...

    async def delete_points(self, ids: Sequence[str]) -> None: ...

    async def scroll_points(
        self,
        filters: Filter | None,
        *,
        limit: int,
        cursor: str | None,
        payload_fields: Sequence[str] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]: ...

    async def query_points(
        self,
        vector: Sequence[float],
        filters: Filter | None,
        *,
        limit: int,
        payload_fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    async def facet_values(self, field: Literal["category", "tags"], *, limit: int) -> list[str]: ...


class QdrantVectorStore:
    PAYLOAD_INDEXES: ClassVar[dict[str, PayloadSchemaType]] = {
        "source": PayloadSchemaType.KEYWORD,
        "ticker": PayloadSchemaType.KEYWORD,
        "event_ticker": PayloadSchemaType.KEYWORD,
        "series_ticker": PayloadSchemaType.KEYWORD,
        "category": PayloadSchemaType.KEYWORD,
        "tags": PayloadSchemaType.KEYWORD,
        "start_datetime": PayloadSchemaType.DATETIME,
        "end_datetime": PayloadSchemaType.DATETIME,
        "yes_ask_price": PayloadSchemaType.FLOAT,
        "yes_bid_price": PayloadSchemaType.FLOAT,
        "yes_ask_size": PayloadSchemaType.FLOAT,
        "yes_bid_size": PayloadSchemaType.FLOAT,
        "volume": PayloadSchemaType.FLOAT,
        "volume_24hr": PayloadSchemaType.FLOAT,
        "open_interest": PayloadSchemaType.FLOAT,
    }

    def __init__(self, client: AsyncQdrantClient, *, collection: str) -> None:
        self._client = client
        self._collection = collection

    async def setup(self, *, vector_size: int) -> None:
        if not await self._client.collection_exists(self._collection):
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info("created collection %s (vector_size=%s)", self._collection, vector_size)
        else:
            logger.info("collection %s already exists", self._collection)

        info = await self._client.get_collection(self._collection)
        existing = info.payload_schema or {}
        for field_name, schema in self.PAYLOAD_INDEXES.items():
            if field_name in existing:
                continue
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field_name,
                field_schema=schema,
            )
            logger.info("created payload index %s (%s)", field_name, schema.value)

    async def get_existing_ids(self, ids: Sequence[str]) -> set[str]:
        if not ids:
            return set()
        id_map = {point_id(ticker): ticker for ticker in ids}
        records = await self._client.retrieve(
            collection_name=self._collection,
            ids=list(id_map),
            with_payload=False,
            with_vectors=False,
        )
        return {id_map[str(record.id)] for record in records if str(record.id) in id_map}

    async def get_payload(self, ticker: str) -> dict[str, Any] | None:
        records = await self._client.retrieve(
            collection_name=self._collection,
            ids=[point_id(ticker)],
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            return None
        return _record_payload(records[0].payload)

    async def upsert_points(self, points: Sequence[VectorPoint]) -> None:
        if not points:
            return
        await self._client.upsert(
            collection_name=self._collection,
            points=[PointStruct(id=point_id(point.id), vector=point.vector, payload=point.payload) for point in points],
        )

    async def update_payloads(self, updates: Sequence[PayloadUpdate]) -> None:
        if not updates:
            return
        existing = await self.get_existing_ids([update.id for update in updates])
        existing_updates = [update for update in updates if update.id in existing]
        if not existing_updates:
            return
        await self._client.batch_update_points(
            collection_name=self._collection,
            update_operations=[
                SetPayloadOperation(
                    set_payload=SetPayload(
                        payload=update.payload,
                        points=[point_id(update.id)],
                    )
                )
                for update in existing_updates
            ],
        )

    async def delete_points(self, ids: Sequence[str]) -> None:
        if not ids:
            return
        await self._client.delete(
            collection_name=self._collection,
            points_selector=[point_id(ticker) for ticker in ids],
        )

    async def scroll_points(
        self,
        filters: Filter | None,
        *,
        limit: int,
        cursor: str | None,
        payload_fields: Sequence[str] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        records, next_page_offset = await self._client.scroll(
            collection_name=self._collection,
            scroll_filter=filters,
            limit=limit,
            offset=cursor,
            with_payload=_payload_selector(payload_fields),
            with_vectors=False,
        )
        payloads = [_record_payload(record.payload) for record in records]
        next_cursor = str(next_page_offset) if next_page_offset is not None else None
        return payloads, next_cursor

    async def query_points(
        self,
        vector: Sequence[float],
        filters: Filter | None,
        *,
        limit: int,
        payload_fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        response = await self._client.query_points(
            collection_name=self._collection,
            query=list(vector),
            query_filter=filters,
            limit=limit,
            with_payload=_payload_selector(payload_fields),
            with_vectors=False,
        )
        return [_record_payload(point.payload) for point in response.points]

    async def facet_values(self, field: Literal["category", "tags"], *, limit: int) -> list[str]:
        response = await self._client.facet(
            collection_name=self._collection,
            key=field,
            limit=limit,
            exact=True,
        )
        return [hit.value for hit in response.hits if isinstance(hit.value, str)]


def _payload_selector(payload_fields: Sequence[str] | None) -> bool | list[str]:
    if payload_fields is None:
        return True
    return list(payload_fields)


def _record_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict(payload) if payload else {}
