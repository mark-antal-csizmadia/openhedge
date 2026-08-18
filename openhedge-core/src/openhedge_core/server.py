import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from openrouter import OpenRouter
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient

from openhedge_core.embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_DIM,
    EmbeddingClient,
    OpenRouterEmbeddingClient,
)
from openhedge_core.filters import MarketFilters, to_qdrant_filter
from openhedge_core.types.market import MARKET_SUMMARY_PAYLOAD_FIELDS, Event, Market, MarketSummary
from openhedge_core.vector_store import (
    DEFAULT_QDRANT_COLLECTION,
    DEFAULT_QDRANT_URL,
    QdrantVectorStore,
    VectorStore,
)

DEFAULT_OPENROUTER_HTTP_REFERER = "https://openhedge.dev"
DEFAULT_OPENROUTER_APP_TITLE = "openhedge"
DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100
DEFAULT_SEARCH_LIMIT = 8
MAX_SEARCH_LIMIT = 20
EVENT_SCROLL_PAGE_SIZE = 100
CATEGORY_FACET_LIMIT = 100
TAG_FACET_SCAN_LIMIT = 1000
DEFAULT_TAG_LIMIT = 20
MAX_TAG_LIMIT = 50

logger = logging.getLogger(__name__)


class MarketHit(BaseModel):
    market: MarketSummary
    score: float | None = None


class MarketPage(BaseModel):
    items: list[MarketHit]
    next_cursor: str | None
    limit: int


class MarketListParams(MarketFilters):
    limit: int = Field(
        default=DEFAULT_PAGE_LIMIT,
        ge=1,
        le=MAX_PAGE_LIMIT,
        description="Page size. Defaults to 20, maximum 100.",
    )
    cursor: str | None = Field(
        default=None,
        description="Pagination cursor from the previous page's next_cursor. Omit for the first page.",
    )


class MarketSearchParams(MarketFilters):
    q: str = Field(
        min_length=1,
        description="Natural-language query embedded and matched against markets.",
    )
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description="Number of nearest neighbors to return. Defaults to 8, maximum 20.",
    )


class VocabList(BaseModel):
    items: list[str]


class TagSearchParams(BaseModel):
    q: str = Field(
        min_length=1,
        description="Case-insensitive substring matched against tag values.",
    )
    limit: int = Field(
        default=DEFAULT_TAG_LIMIT,
        ge=1,
        le=MAX_TAG_LIMIT,
        description="Maximum number of matching tags to return. Defaults to 20, maximum 50.",
    )


def create_app(*, store: VectorStore | None = None, embedder: EmbeddingClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if store is not None:
            yield
            return

        qdrant = AsyncQdrantClient(
            url=os.environ.get("QDRANT_URL", DEFAULT_QDRANT_URL),
            api_key=os.environ.get("QDRANT_API_KEY") or None,
        )
        try:
            app.state.store = QdrantVectorStore(
                qdrant,
                collection=os.environ.get("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION),
            )
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                logger.warning("OPENROUTER_API_KEY is not set; /search will return 503")
                app.state.embedder = None
                yield
                return
            model = os.environ.get("OPENROUTER_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
            dimensions = int(os.environ.get("OPENROUTER_EMBEDDING_DIM", str(EMBEDDING_DIM)))
            async with OpenRouter(
                api_key=api_key,
                http_referer=DEFAULT_OPENROUTER_HTTP_REFERER,
                x_open_router_title=DEFAULT_OPENROUTER_APP_TITLE,
            ) as openrouter_client:
                app.state.embedder = OpenRouterEmbeddingClient(
                    openrouter_client,
                    model=model,
                    dimensions=dimensions,
                )
                yield
        finally:
            await qdrant.close()

    app = FastAPI(title="openhedge", lifespan=lifespan)
    if store is not None:
        app.state.store = store
        app.state.embedder = embedder
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/markets", browse_markets, methods=["GET"], response_model=MarketPage)
    app.add_api_route("/markets/{ticker}", get_market, methods=["GET"], response_model=Market)
    app.add_api_route("/events/{event_ticker}", get_event, methods=["GET"], response_model=Event)
    app.add_api_route("/search", search_markets, methods=["POST"], response_model=MarketPage)
    app.add_api_route("/categories", list_categories, methods=["GET"], response_model=VocabList)
    app.add_api_route("/tags", search_tags, methods=["GET"], response_model=VocabList)
    return app


async def health() -> dict[str, str]:
    return {"status": "ok"}


async def browse_markets(
    request: Request,
    params: Annotated[MarketListParams, Query()],
) -> MarketPage:
    store: VectorStore = request.app.state.store
    payloads, next_cursor = await store.scroll_points(
        to_qdrant_filter(params),
        limit=params.limit,
        cursor=params.cursor or None,
        payload_fields=MARKET_SUMMARY_PAYLOAD_FIELDS,
    )
    return MarketPage(
        items=[MarketHit(market=MarketSummary.model_validate(payload)) for payload in payloads],
        next_cursor=next_cursor,
        limit=params.limit,
    )


async def search_markets(
    request: Request,
    params: MarketSearchParams,
) -> MarketPage:
    embedder: EmbeddingClient | None = request.app.state.embedder
    if embedder is None:
        raise HTTPException(status_code=503, detail="search is unavailable: embeddings are not configured")

    vectors = await embedder.embed_batch([params.q])
    if len(vectors) != 1:
        raise HTTPException(status_code=502, detail="embedding failed")

    store: VectorStore = request.app.state.store
    hits = await store.query_points(
        vectors[0],
        to_qdrant_filter(params),
        limit=params.limit,
        payload_fields=MARKET_SUMMARY_PAYLOAD_FIELDS,
    )
    return MarketPage(
        items=[MarketHit(market=MarketSummary.model_validate(payload), score=score) for payload, score in hits],
        next_cursor=None,
        limit=params.limit,
    )


async def get_market(request: Request, ticker: str) -> Market:
    store: VectorStore = request.app.state.store
    payload = await store.get_payload(ticker)
    if payload is None:
        raise HTTPException(status_code=404, detail="market not found")
    return Market.model_validate(payload)


async def get_event(request: Request, event_ticker: str) -> Event:
    store: VectorStore = request.app.state.store
    qfilter = to_qdrant_filter(MarketFilters(event_ticker=[event_ticker]))
    payloads: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page, cursor = await store.scroll_points(
            qfilter,
            limit=EVENT_SCROLL_PAGE_SIZE,
            cursor=cursor,
            payload_fields=MARKET_SUMMARY_PAYLOAD_FIELDS,
        )
        payloads.extend(page)
        if cursor is None:
            break
    if not payloads:
        raise HTTPException(status_code=404, detail="event not found")
    markets = [MarketSummary.model_validate(payload) for payload in payloads]
    return Event.from_markets(markets)


async def list_categories(request: Request) -> VocabList:
    store: VectorStore = request.app.state.store
    values = await store.facet_values("category", limit=CATEGORY_FACET_LIMIT)
    return VocabList(items=sorted(values))


async def search_tags(
    request: Request,
    params: Annotated[TagSearchParams, Query()],
) -> VocabList:
    store: VectorStore = request.app.state.store
    values = await store.facet_values("tags", limit=TAG_FACET_SCAN_LIMIT)
    needle = params.q.casefold()
    matched = [value for value in values if needle in value.casefold()]
    return VocabList(items=matched[: params.limit])


app = create_app()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        app,
        host=os.environ.get("API_HOST", "0.0.0.0"),
        port=int(os.environ.get("API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
