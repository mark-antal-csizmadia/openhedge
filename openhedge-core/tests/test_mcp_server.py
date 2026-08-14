from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from openhedge_core.api_client import OpenhedgeApiError
from openhedge_core.mcp_server import create_mcp
from openhedge_core.server import MarketHit, MarketListParams, MarketPage, MarketSearchParams
from openhedge_core.types.market import Event, Market, MarketSource


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


class FakeApiClient:
    def __init__(self) -> None:
        self.browse_calls: list[MarketListParams] = []
        self.search_calls: list[MarketSearchParams] = []
        self.get_market_calls: list[str] = []
        self.get_event_calls: list[str] = []
        self.browse_result: MarketPage | None = None
        self.search_result: MarketPage | None = None
        self.markets: dict[str, Market] = {}
        self.events: dict[str, Event] = {}
        self.errors: dict[str, OpenhedgeApiError] = {}

    async def browse_markets(self, params: MarketListParams) -> MarketPage:
        self.browse_calls.append(params)
        if "browse" in self.errors:
            raise self.errors["browse"]
        assert self.browse_result is not None
        return self.browse_result

    async def search_markets(self, params: MarketSearchParams) -> MarketPage:
        self.search_calls.append(params)
        if "search" in self.errors:
            raise self.errors["search"]
        assert self.search_result is not None
        return self.search_result

    async def get_market(self, ticker: str) -> Market:
        self.get_market_calls.append(ticker)
        if ticker in self.errors:
            raise self.errors[ticker]
        return self.markets[ticker]

    async def get_event(self, event_ticker: str) -> Event:
        self.get_event_calls.append(event_ticker)
        if event_ticker in self.errors:
            raise self.errors[event_ticker]
        return self.events[event_ticker]


def _schema_text(schema: dict[str, Any]) -> str:
    return str(schema).lower()


@pytest.mark.asyncio
async def test_list_tools_documents_api_surface() -> None:
    mcp = create_mcp(api_client=FakeApiClient())
    async with Client(mcp) as client:
        tools = await client.list_tools()
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == {"browse_markets", "search_markets", "get_market", "get_event"}
    for tool in tools:
        assert tool.description
        assert len(tool.description) > 40

    browse_schema = by_name["browse_markets"].inputSchema
    search_schema = by_name["search_markets"].inputSchema
    get_market_schema = by_name["get_market"].inputSchema
    get_event_schema = by_name["get_event"].inputSchema
    assert "q" in _schema_text(search_schema)
    assert "cursor" in _schema_text(browse_schema)
    assert "category" in _schema_text(browse_schema)
    assert "price_yes_gte" in _schema_text(browse_schema)
    assert "probabilities" in _schema_text(browse_schema)
    assert "ticker" in _schema_text(get_market_schema)
    assert "event_ticker" in _schema_text(get_event_schema)
    assert "natural-language" in (by_name["search_markets"].description or "").lower()
    assert "strike_order" in (by_name["get_event"].description or "")


@pytest.mark.asyncio
async def test_browse_markets_forwards_params() -> None:
    api = FakeApiClient()
    market = _market(ticker="MKT-1")
    api.browse_result = MarketPage(items=[MarketHit(market=market)], next_cursor="next-page", limit=5)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "browse_markets",
            {"params": {"category": ["Politics"], "price_yes_gte": 0.2, "limit": 5, "cursor": "abc"}},
        )
    assert len(api.browse_calls) == 1
    call = api.browse_calls[0]
    assert call.category == ["Politics"]
    assert call.price_yes_gte == pytest.approx(0.2)
    assert call.limit == 5
    assert call.cursor == "abc"
    page = MarketPage.model_validate(result.structured_content)
    assert page.next_cursor == "next-page"
    assert page.items[0].market.ticker == "MKT-1"


@pytest.mark.asyncio
async def test_search_markets_forwards_query() -> None:
    api = FakeApiClient()
    market = _market(ticker="MKT-0")
    api.search_result = MarketPage(items=[MarketHit(market=market, score=0.9)], next_cursor="2", limit=2)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_markets",
            {"params": {"q": "oil prices", "limit": 2, "tags": ["fed"]}},
        )
    assert api.search_calls[0].q == "oil prices"
    assert api.search_calls[0].tags == ["fed"]
    page = MarketPage.model_validate(result.structured_content)
    assert page.items[0].score == pytest.approx(0.9)
    assert page.next_cursor == "2"


@pytest.mark.asyncio
async def test_get_market_and_event() -> None:
    api = FakeApiClient()
    markets = [
        _market(ticker="MKT-0", strike_order=0),
        _market(ticker="MKT-1", strike_order=1),
    ]
    api.markets["MKT-1"] = markets[1]
    api.events["EVT-OPEN"] = Event.from_markets(markets)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        market_result = await client.call_tool("get_market", {"ticker": "MKT-1"})
        event_result = await client.call_tool("get_event", {"event_ticker": "EVT-OPEN"})
    assert api.get_market_calls == ["MKT-1"]
    assert api.get_event_calls == ["EVT-OPEN"]
    assert Market.model_validate(market_result.structured_content).ticker == "MKT-1"
    event = Event.model_validate(event_result.structured_content)
    assert [market.ticker for market in event.markets] == ["MKT-0", "MKT-1"]


@pytest.mark.asyncio
async def test_get_market_missing_is_tool_error() -> None:
    api = FakeApiClient()
    api.errors["MISSING"] = OpenhedgeApiError(404, "market not found")
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="market not found"):
            await client.call_tool("get_market", {"ticker": "MISSING"})


@pytest.mark.asyncio
async def test_search_unavailable_is_tool_error() -> None:
    api = FakeApiClient()
    api.errors["search"] = OpenhedgeApiError(503, "search is unavailable: embeddings are not configured")
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="embeddings are not configured"):
            await client.call_tool("search_markets", {"params": {"q": "oil"}})


@pytest.mark.asyncio
async def test_health_route() -> None:
    mcp = create_mcp(api_client=FakeApiClient())
    app = mcp.http_app(stateless_http=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
