from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from aiolimiter import AsyncLimiter
from openhedge_core.apis.kalshi import (
    EVENTS_URL,
    GetEventsRequest,
    get_events,
    produce_closed_markets,
    produce_events,
    produce_open_markets,
)
from openhedge_core.types.kalshi import GetEventsResponse, KalshiEventStatus, KalshiMarketStatus
from pydantic import ValidationError

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
    "category": "Politics",
    "markets": [MARKET_ACTIVE, MARKET_CLOSED],
}

EVENT_CLOSED = {
    "event_ticker": "EVT-CLOSED",
    "title": "Closed event",
    "series_ticker": "SERIES",
    "category": "Politics",
    "markets": [MARKET_CLOSED],
}


def _json_response(status_code: int, payload: dict[str, Any] | str) -> httpx.Response:
    if isinstance(payload, str):
        return httpx.Response(status_code, text=payload)
    return httpx.Response(status_code, json=payload)


@pytest.fixture
def limiter() -> AsyncLimiter:
    return AsyncLimiter(max_rate=1000, time_period=1)


@pytest.mark.asyncio
async def test_get_events_does_not_retry_400(limiter: AsyncLimiter) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _json_response(400, {"error": "bad request"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await get_events(client, limiter, GetEventsRequest(status=KalshiEventStatus.OPEN))

    assert exc_info.value.response.status_code == 400
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_get_events_retries_429_then_succeeds(limiter: AsyncLimiter) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return _json_response(429, {"error": "too many requests"})
        return _json_response(200, {"events": [], "cursor": None})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch("tenacity.nap.sleep", return_value=None), patch("asyncio.sleep", new_callable=AsyncMock):
            envelope = await get_events(client, limiter, GetEventsRequest(status=KalshiEventStatus.OPEN))

    assert calls["n"] == 3
    assert envelope.events == []
    assert envelope.cursor is None


@pytest.mark.asyncio
async def test_get_events_retries_503_then_succeeds(limiter: AsyncLimiter) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _json_response(503, {"error": "unavailable"})
        return _json_response(200, {"events": [EVENT_OPEN], "cursor": None})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch("tenacity.nap.sleep", return_value=None), patch("asyncio.sleep", new_callable=AsyncMock):
            envelope = await get_events(client, limiter, GetEventsRequest(status=KalshiEventStatus.OPEN))

    assert calls["n"] == 2
    assert len(envelope.events) == 1


@pytest.mark.asyncio
async def test_get_events_missing_events_raises_validation_error(limiter: AsyncLimiter) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, {"cursor": None})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValidationError):
            await get_events(client, limiter, GetEventsRequest(status=KalshiEventStatus.OPEN))


@pytest.mark.asyncio
async def test_produce_events_does_not_mutate_params(limiter: AsyncLimiter) -> None:
    pages: list[dict[str, Any]] = [
        {"events": [EVENT_OPEN], "cursor": "page-2"},
        {"events": [EVENT_CLOSED], "cursor": None},
    ]
    call_idx = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = pages[call_idx["n"]]
        call_idx["n"] += 1
        return _json_response(200, payload)

    params = GetEventsRequest(status=KalshiEventStatus.OPEN, cursor=None)
    original = params.model_dump()

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        collected: list[GetEventsResponse] = []
        async for envelope in produce_events(client, limiter, params):
            collected.append(envelope)

    assert params.model_dump() == original
    assert params.cursor is None
    assert len(collected) == 2
    assert collected[0].cursor == "page-2"
    assert collected[1].cursor is None


@pytest.mark.asyncio
async def test_produce_closed_markets_paginates_open_then_closed(limiter: AsyncLimiter) -> None:
    statuses: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(EVENTS_URL)
        status = request.url.params.get("status")
        statuses.append(status)
        if status == KalshiEventStatus.OPEN:
            return _json_response(200, {"events": [EVENT_OPEN], "cursor": None})
        if status == KalshiEventStatus.CLOSED:
            return _json_response(200, {"events": [EVENT_CLOSED], "cursor": None})
        raise AssertionError(f"unexpected status={status!r}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        items = [item async for item in produce_closed_markets(client=client, limiter=limiter)]

    assert statuses == [KalshiEventStatus.OPEN, KalshiEventStatus.CLOSED]
    assert [market.ticker for _, market, _ in items] == ["MKT-CLOSED", "MKT-CLOSED"]
    assert all(market.status == KalshiMarketStatus.CLOSED for _, market, _ in items)
    assert [strike_order for _, _, strike_order in items] == [1, 0]


@pytest.mark.asyncio
async def test_produce_open_markets_yields_active_only(limiter: AsyncLimiter) -> None:
    statuses: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(EVENTS_URL)
        status = request.url.params.get("status")
        statuses.append(status)
        if status == KalshiEventStatus.OPEN:
            return _json_response(200, {"events": [EVENT_OPEN], "cursor": None})
        raise AssertionError(f"unexpected status={status!r}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        items = [item async for item in produce_open_markets(client=client, limiter=limiter)]

    assert statuses == [KalshiEventStatus.OPEN]
    assert [market.ticker for _, market, _ in items] == ["MKT-ACTIVE"]
    assert all(market.status == KalshiMarketStatus.ACTIVE for _, market, _ in items)
    assert [strike_order for _, _, strike_order in items] == [0]
