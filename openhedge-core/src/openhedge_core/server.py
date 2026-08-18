import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from openrouter import OpenRouter
from pydantic import BaseModel, Field, ValidationError
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
MAX_EVENT_MARKETS = 50
DEFAULT_VOCAB_LIMIT = 20
MAX_VOCAB_LIMIT = 100

logger = logging.getLogger(__name__)


class MarketPage(BaseModel):
    items: list[MarketSummary]
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


class VocabListParams(BaseModel):
    limit: int = Field(
        default=DEFAULT_VOCAB_LIMIT,
        ge=1,
        le=MAX_VOCAB_LIMIT,
        description="Number of most popular facet values to return. Defaults to 20, maximum 100.",
    )


class VocabList(BaseModel):
    items: list[str]
    truncated: bool = Field(
        description="True when the facet list was capped at limit; more values may exist.",
    )
    limit: int


class ReadyStatus(BaseModel):
    status: str
    qdrant: str
    embedder: str


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
    app.add_api_route("/ready", ready, methods=["GET"], response_model=ReadyStatus)
    app.add_api_route("/markets", browse_markets, methods=["GET"], response_model=MarketPage)
    app.add_api_route("/markets/{ticker}", get_market, methods=["GET"], response_model=Market)
    app.add_api_route("/events/{event_ticker}", get_event, methods=["GET"], response_model=Event)
    app.add_api_route("/search", search_markets, methods=["POST"], response_model=MarketPage)
    app.add_api_route("/categories", list_categories, methods=["GET"], response_model=VocabList)
    app.add_api_route("/tags", list_tags, methods=["GET"], response_model=VocabList)
    return app


async def health() -> dict[str, str]:
    return {"status": "ok"}


async def ready(request: Request) -> ReadyStatus:
    store: VectorStore = request.app.state.store
    try:
        await store.ready()
    except Exception:
        logger.exception("readiness check failed")
        raise HTTPException(status_code=503, detail="not ready") from None
    embedder: EmbeddingClient | None = request.app.state.embedder
    return ReadyStatus(
        status="ok",
        qdrant="ok",
        embedder="ok" if embedder is not None else "unconfigured",
    )


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
        items=_market_summaries(payloads),
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
    payloads = await store.query_points(
        vectors[0],
        to_qdrant_filter(params),
        limit=params.limit,
        payload_fields=MARKET_SUMMARY_PAYLOAD_FIELDS,
    )
    return MarketPage(
        items=_market_summaries(payloads),
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
    markets = _market_summaries(payloads)
    if not markets:
        raise HTTPException(status_code=404, detail="event not found")
    return Event.from_markets(markets, limit=MAX_EVENT_MARKETS)


async def list_categories(
    request: Request,
    params: Annotated[VocabListParams, Query()],
) -> VocabList:
    return await _list_vocab(request.app.state.store, "category", params)


async def list_tags(
    request: Request,
    params: Annotated[VocabListParams, Query()],
) -> VocabList:
    return await _list_vocab(request.app.state.store, "tags", params)


async def _list_vocab(
    store: VectorStore,
    field: Literal["category", "tags"],
    params: VocabListParams,
) -> VocabList:
    values = await store.facet_values(field, limit=params.limit)
    return VocabList(items=values, truncated=len(values) == params.limit, limit=params.limit)


def _market_summaries(payloads: list[dict[str, Any]]) -> list[MarketSummary]:
    items: list[MarketSummary] = []
    for payload in payloads:
        try:
            items.append(MarketSummary.model_validate(payload))
        except ValidationError as exc:
            ticker = payload.get("ticker")
            logger.warning("skipping invalid market payload ticker=%s: %s", ticker, exc)
    return items


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
