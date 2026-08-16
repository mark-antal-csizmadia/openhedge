import json
import logging
from collections.abc import AsyncIterator

import httpx
import tenacity
from aiolimiter import AsyncLimiter
from pydantic import BaseModel, Field, PositiveInt

from openhedge_core.types.kalshi import (
    GetKalshiEventsResponse,
    GetKalshiSeriesResponse,
    KalshiEvent,
    KalshiEventStatus,
    KalshiMarket,
    KalshiMarketStatus,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
EVENTS_URL = f"{BASE_URL}/events"
SERIES_URL = f"{BASE_URL}/series"

RETRY_STOP_AFTER_ATTEMPT = 3
RETRY_WAIT_MULTIPLIER = 1
RETRY_WAIT_MIN = 4
RETRY_WAIT_MAX = 15

# Kalshi Basic Read: 200 tokens/s, default GET cost 10 tokens → ~20 rps.
# https://docs.kalshi.com/getting_started/rate_limits
MAX_RATE = 20
TIME_PERIOD = 1

EVENTS_LIMIT = 200

CLOSED_MARKET_STATUSES: frozenset[KalshiMarketStatus] = frozenset(
    {
        KalshiMarketStatus.CLOSED,
        KalshiMarketStatus.DETERMINED,
        KalshiMarketStatus.FINALIZED,
    }
)
OPEN_MARKET_STATUSES: frozenset[KalshiMarketStatus] = frozenset({KalshiMarketStatus.ACTIVE})
OPEN_EVENT_STATUSES: frozenset[KalshiEventStatus] = frozenset({KalshiEventStatus.OPEN})
OPEN_AND_CLOSED_EVENT_STATUSES: frozenset[KalshiEventStatus] = frozenset(
    {KalshiEventStatus.OPEN, KalshiEventStatus.CLOSED}
)


class GetEventsRequest(BaseModel):
    """Request parameters for the Kalshi REST API get events endpoint."""

    # note: limit max value is 200, see https://docs.kalshi.com/api-reference/events/get-events#parameter-limit
    limit: PositiveInt = Field(default=200, le=200)
    cursor: str | None = None
    with_nested_markets: bool = True
    status: KalshiEventStatus | None = None


class GetSeriesRequest(BaseModel):
    """Request parameters for the Kalshi REST API get series endpoint."""

    series_ticker: str


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, json.JSONDecodeError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


@tenacity.retry(
    stop=tenacity.stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
    wait=tenacity.wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    retry=tenacity.retry_if_exception(_is_retryable),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def get_events(
    client: httpx.AsyncClient, limiter: AsyncLimiter, params: GetEventsRequest
) -> GetKalshiEventsResponse:
    """Get events from the Kalshi REST API."""
    async with limiter:
        response = await client.get(url=EVENTS_URL, params=params.model_dump(mode="json", exclude_none=True))
    response.raise_for_status()
    return GetKalshiEventsResponse.model_validate(response.json())


@tenacity.retry(
    stop=tenacity.stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
    wait=tenacity.wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    retry=tenacity.retry_if_exception(_is_retryable),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def get_series(
    client: httpx.AsyncClient, limiter: AsyncLimiter, params: GetSeriesRequest
) -> GetKalshiSeriesResponse:
    """Get series from the Kalshi REST API."""
    async with limiter:
        response = await client.get(url=f"{SERIES_URL}/{params.series_ticker}")
    response.raise_for_status()
    return GetKalshiSeriesResponse.model_validate(response.json())


async def produce_events(
    client: httpx.AsyncClient,
    limiter: AsyncLimiter,
    params: GetEventsRequest,
) -> AsyncIterator[GetKalshiEventsResponse]:
    """Paginate Kalshi events without mutating the caller's request."""
    cursor = params.cursor
    while True:
        page_params = params.model_copy(update={"cursor": cursor})
        envelope = await get_events(client, limiter, page_params)
        yield envelope
        if not envelope.cursor:
            break
        cursor = envelope.cursor


async def produce_markets(
    client: httpx.AsyncClient,
    limiter: AsyncLimiter,
    *,
    event_statuses: frozenset[KalshiEventStatus],
    market_statuses: frozenset[KalshiMarketStatus],
) -> AsyncIterator[tuple[KalshiEvent, KalshiMarket, int]]:
    for status in KalshiEventStatus:
        if status not in event_statuses:
            continue
        params = GetEventsRequest(status=status, with_nested_markets=True, limit=EVENTS_LIMIT)
        async for envelope in produce_events(client, limiter, params):
            for event in envelope.events:
                for strike_order, market in enumerate(event.markets):
                    if market.status in market_statuses:
                        yield event, market, strike_order


async def produce_open_markets(
    client: httpx.AsyncClient,
    limiter: AsyncLimiter,
) -> AsyncIterator[tuple[KalshiEvent, KalshiMarket, int]]:
    """Yield active markets under open events."""
    async for item in produce_markets(
        client,
        limiter,
        event_statuses=OPEN_EVENT_STATUSES,
        market_statuses=OPEN_MARKET_STATUSES,
    ):
        yield item


async def produce_closed_markets(
    client: httpx.AsyncClient,
    limiter: AsyncLimiter,
) -> AsyncIterator[tuple[KalshiEvent, KalshiMarket, int]]:
    """Yield closed markets under open and closed events."""
    async for item in produce_markets(
        client,
        limiter,
        event_statuses=OPEN_AND_CLOSED_EVENT_STATUSES,
        market_statuses=CLOSED_MARKET_STATUSES,
    ):
        yield item
