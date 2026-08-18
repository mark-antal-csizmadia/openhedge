import asyncio
import logging
import signal
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
from aiolimiter import AsyncLimiter
from openrouter import OpenRouter
from qdrant_client import AsyncQdrantClient

from openhedge_core.apis.kalshi import (
    MAX_RATE,
    TIME_PERIOD,
    GetSeriesRequest,
    get_series,
    produce_closed_markets,
    produce_open_markets,
)
from openhedge_core.consumer import Consumer
from openhedge_core.embeddings import EmbeddingClient, OpenRouterEmbeddingClient, market_embedding_text
from openhedge_core.producer import Producer
from openhedge_core.settings import SyncMarketsSettings
from openhedge_core.types.kalshi import KalshiSeries
from openhedge_core.types.market import Market
from openhedge_core.vector_store import PayloadUpdate, QdrantVectorStore, VectorPoint, VectorStore

logger = logging.getLogger(__name__)

HTTP_MAX_CONNECTIONS = 2
HTTP_MAX_KEEPALIVE_CONNECTIONS = 2
HTTP_TIMEOUT = 30.0


def http_client() -> httpx.AsyncClient:
    """Create an HTTP client sized for concurrent open and closed event pagination."""
    return httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=HTTP_MAX_CONNECTIONS,
            max_keepalive_connections=HTTP_MAX_KEEPALIVE_CONNECTIONS,
        ),
        timeout=httpx.Timeout(HTTP_TIMEOUT, pool=HTTP_TIMEOUT),
    )


class SeriesCache:
    def __init__(self, client: httpx.AsyncClient, limiter: AsyncLimiter) -> None:
        self._client = client
        self._limiter = limiter
        self._cache: dict[str, KalshiSeries] = {}
        self._lock = asyncio.Lock()

    async def get(self, series_ticker: str) -> KalshiSeries:
        cached = self._cache.get(series_ticker)
        if cached is not None:
            return cached
        async with self._lock:
            cached = self._cache.get(series_ticker)
            if cached is not None:
                return cached
            response = await get_series(
                self._client,
                self._limiter,
                GetSeriesRequest(series_ticker=series_ticker),
            )
            self._cache[series_ticker] = response.series
            return response.series


async def consume_open_batch(
    batch: list[Market],
    *,
    embedder: EmbeddingClient,
    store: VectorStore,
) -> None:
    if not batch:
        return
    existing = await store.get_existing_ids([market.ticker for market in batch])
    to_create = [market for market in batch if market.ticker not in existing]
    to_update = [market for market in batch if market.ticker in existing]
    if to_create:
        vectors = await embedder.embed_batch([market_embedding_text(market) for market in to_create])
        await store.upsert_points(
            [
                VectorPoint(id=market.ticker, vector=vector, payload=market.payload())
                for market, vector in zip(to_create, vectors, strict=True)
            ]
        )
    if to_update:
        await store.update_payloads([PayloadUpdate(id=market.ticker, payload=market.payload()) for market in to_update])
    logger.info("open batch created=%s updated=%s", len(to_create), len(to_update))


async def consume_closed_batch(batch: list[str], *, store: VectorStore) -> None:
    if not batch:
        return
    await store.delete_points(batch)
    logger.info("closed batch deleted=%s", len(batch))


async def _run_pipeline[T](
    name: str,
    produce_fn: Callable[[], AsyncIterator[T]],
    consume_fn: Callable[[list[T]], Awaitable[None]],
    *,
    batch_size: int,
    shutdown_event: asyncio.Event,
) -> None:
    queue: asyncio.Queue[T] = asyncio.Queue(maxsize=2 * batch_size)
    producers_done = asyncio.Event()
    producer = Producer(name=name, produce_fn=produce_fn, queue=queue, shutdown_event=shutdown_event)
    consumer = Consumer(
        name=name,
        consume_fn=consume_fn,
        queue=queue,
        shutdown_event=shutdown_event,
        batch_size=batch_size,
        producers_done=producers_done,
    )

    async def produce_then_signal() -> None:
        try:
            await producer.run()
        finally:
            producers_done.set()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(produce_then_signal(), name=f"{name}-producer")
        tg.create_task(consumer.run(), name=f"{name}-consumer")


def _install_signal_handlers(shutdown_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)


async def run(
    *,
    client: httpx.AsyncClient,
    limiter: AsyncLimiter,
    embedder: EmbeddingClient,
    store: VectorStore,
    batch_size: int = 100,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    shutdown_event = shutdown_event or asyncio.Event()
    series_cache = SeriesCache(client, limiter)

    async def produce_open() -> AsyncIterator[Market]:
        async for event, market, strike_order in produce_open_markets(client=client, limiter=limiter):
            series = await series_cache.get(event.series_ticker)
            yield Market.from_kalshi_rest_api(event, market, series, strike_order=strike_order)

    async def produce_closed() -> AsyncIterator[str]:
        async for _, market, _ in produce_closed_markets(client=client, limiter=limiter):
            yield market.ticker

    async def consume_open(batch: list[Market]) -> None:
        await consume_open_batch(batch, embedder=embedder, store=store)

    async def consume_closed(batch: list[str]) -> None:
        await consume_closed_batch(batch, store=store)

    results = await asyncio.gather(
        _run_pipeline(
            "open",
            produce_open,
            consume_open,
            batch_size=batch_size,
            shutdown_event=shutdown_event,
        ),
        _run_pipeline(
            "closed",
            produce_closed,
            consume_closed,
            batch_size=batch_size,
            shutdown_event=shutdown_event,
        ),
        return_exceptions=True,
    )
    errors = [result for result in results if isinstance(result, BaseException)]
    if errors:
        raise BaseExceptionGroup("market sync failed", errors)


async def async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    shutdown_event = asyncio.Event()
    _install_signal_handlers(shutdown_event)
    limiter = AsyncLimiter(max_rate=MAX_RATE, time_period=TIME_PERIOD)
    settings = SyncMarketsSettings()
    qdrant = AsyncQdrantClient(
        url=settings.qdrant.url,
        api_key=settings.qdrant.api_key,
    )
    try:
        async with OpenRouter(
            api_key=settings.openrouter.api_key,
            http_referer=settings.openrouter.http_referer,
            x_open_router_title=settings.openrouter.app_title,
        ) as openrouter_client:
            store = QdrantVectorStore(
                qdrant,
                collection=settings.qdrant.collection,
                point_id_namespace=settings.qdrant.point_id_namespace,
            )
            embedder = OpenRouterEmbeddingClient(
                openrouter_client,
                model=settings.openrouter.embedding_model,
                dimensions=settings.openrouter.embedding_dim,
            )
            async with http_client() as client:
                await run(
                    client=client,
                    limiter=limiter,
                    embedder=embedder,
                    store=store,
                    batch_size=settings.batch_size,
                    shutdown_event=shutdown_event,
                )
    finally:
        await qdrant.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
