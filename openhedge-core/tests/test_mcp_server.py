from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from openhedge_core.api_client import OpenhedgeApiError
from openhedge_core.hedge import HEDGE_MATH_MARKDOWN, HedgeCandidate
from openhedge_core.mcp_server import INSTRUCTIONS, create_mcp
from openhedge_core.server import (
    MarketListParams,
    MarketPage,
    MarketSearchParams,
    ReadyStatus,
    VocabList,
    VocabListParams,
)
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


class FakeApiClient:
    def __init__(self) -> None:
        self.browse_calls: list[MarketListParams] = []
        self.search_calls: list[MarketSearchParams] = []
        self.get_market_calls: list[str] = []
        self.get_event_calls: list[str] = []
        self.list_categories_calls: list[VocabListParams] = []
        self.list_tags_calls: list[VocabListParams] = []
        self.browse_result: MarketPage | None = None
        self.search_result: MarketPage | None = None
        self.categories_result: VocabList | None = None
        self.tags_result: VocabList | None = None
        self.markets: dict[str, Market] = {}
        self.events: dict[str, Event] = {}
        self.errors: dict[str, OpenhedgeApiError] = {}
        self.ready_result = ReadyStatus(status="ok", qdrant="ok", embedder="ok")

    async def ready(self) -> ReadyStatus:
        if "ready" in self.errors:
            raise self.errors["ready"]
        return self.ready_result

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

    async def list_categories(self, params: VocabListParams) -> VocabList:
        self.list_categories_calls.append(params)
        if "categories" in self.errors:
            raise self.errors["categories"]
        assert self.categories_result is not None
        return self.categories_result

    async def list_tags(self, params: VocabListParams) -> VocabList:
        self.list_tags_calls.append(params)
        if "tags" in self.errors:
            raise self.errors["tags"]
        assert self.tags_result is not None
        return self.tags_result


def _schema_text(schema: dict[str, Any]) -> str:
    return str(schema).lower()


def _param_properties(schema: dict[str, Any]) -> dict[str, Any]:
    props = schema.get("properties") or {}
    params = props.get("params")
    if isinstance(params, dict):
        nested = params.get("properties")
        if isinstance(nested, dict):
            return nested
    return props


@pytest.mark.asyncio
async def test_list_tools_documents_api_surface() -> None:
    mcp = create_mcp(api_client=FakeApiClient())
    async with Client(mcp) as client:
        tools = await client.list_tools()
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == {
        "hedge",
        "browse_markets",
        "search_markets",
        "get_market",
        "get_event",
        "list_categories",
        "list_tags",
    }
    titles = {tool.name: tool.title for tool in tools}
    assert titles["hedge"] == "Hedge a risk"
    assert titles["browse_markets"] == "Browse markets"
    assert titles["search_markets"] == "Search markets"
    assert titles["get_market"] == "Get a market"
    assert titles["get_event"] == "Get an event"
    assert titles["list_categories"] == "List categories"
    assert titles["list_tags"] == "List tags"
    for tool in tools:
        assert tool.description
        assert len(tool.description) > 40

    hedge_schema = by_name["hedge"].inputSchema
    browse_schema = by_name["browse_markets"].inputSchema
    search_schema = by_name["search_markets"].inputSchema
    get_market_schema = by_name["get_market"].inputSchema
    get_event_schema = by_name["get_event"].inputSchema
    list_tags_schema = by_name["list_tags"].inputSchema
    list_categories_schema = by_name["list_categories"].inputSchema
    assert "q" in _schema_text(search_schema)
    assert "cursor" not in _param_properties(search_schema)
    assert "cursor" in _param_properties(browse_schema)
    assert "numeric offset" not in INSTRUCTIONS.lower()
    assert "category" in _schema_text(browse_schema)
    assert "tags_mode" in _schema_text(browse_schema)
    assert "tags_mode" in _schema_text(search_schema)
    assert "yes_ask_price_gte" in _schema_text(browse_schema)
    assert "dollars" in _schema_text(browse_schema)
    assert "ticker" in _schema_text(get_market_schema)
    assert "event_ticker" in _schema_text(get_event_schema)
    assert "q" not in _param_properties(list_tags_schema)
    assert "q" not in _param_properties(list_categories_schema)
    assert "limit" in _param_properties(list_tags_schema)
    assert "limit" in _param_properties(list_categories_schema)
    assert "cursor" not in _param_properties(list_tags_schema)
    assert "cursor" not in _param_properties(list_categories_schema)
    hedge_props = _param_properties(hedge_schema)
    assert "ticker" in hedge_props
    assert "legs" not in hedge_props
    assert "params" not in (hedge_schema.get("properties") or {})
    assert "ticker" in _schema_text(hedge_schema)
    assert "estimated_hit_dollars" in _schema_text(hedge_schema)
    assert "risk" not in _schema_text(hedge_schema)
    assert "natural-language" in (by_name["search_markets"].description or "").lower()
    assert "strike_order" in (by_name["get_event"].description or "")
    get_event_description = (by_name["get_event"].description or "").lower()
    assert "all of its markets" in get_event_description
    assert "truncated" not in get_event_description
    assert "capped" not in get_event_description
    assert "truncated" in INSTRUCTIONS.lower()
    assert "get_event returns all markets" in INSTRUCTIONS.lower()
    assert "browse_markets" in INSTRUCTIONS
    assert "compact" in (by_name["browse_markets"].description or "").lower()
    assert "compact" in (by_name["search_markets"].description or "").lower()
    search_description = (by_name["search_markets"].description or "").lower()
    browse_description = (by_name["browse_markets"].description or "").lower()
    assert "score" not in search_description
    assert "score" not in browse_description
    assert "end_datetime" in search_description
    assert "nearest neighbors" in search_description
    assert "end_datetime" in INSTRUCTIONS
    assert "expired" not in search_description
    assert "expired" not in browse_description
    assert "expired" not in INSTRUCTIONS.lower()
    assert "all returned markets are open" in search_description
    assert "all returned markets are open" in browse_description
    assert "all returned markets are open" in INSTRUCTIONS.lower()
    assert "compact" in (by_name["get_event"].description or "").lower()
    assert "description" in (by_name["get_market"].description or "").lower()
    assert "category" in (by_name["list_categories"].description or "").lower()
    assert "truncated" in (by_name["list_categories"].description or "").lower()
    assert "full set" not in (by_name["list_categories"].description or "").lower()
    assert "truncated" in (by_name["list_tags"].description or "").lower()
    assert "substring" not in (by_name["list_tags"].description or "").lower()
    assert "full set" not in INSTRUCTIONS.lower()
    assert "substring" not in INSTRUCTIONS.lower()
    assert "tags_mode=all" in INSTRUCTIONS
    assert "legs" not in INSTRUCTIONS.lower()
    hedge_description = (by_name["hedge"].description or "").lower()
    assert "ticker" in hedge_description
    assert "search_markets" in hedge_description
    assert "does not place orders" in hedge_description


@pytest.mark.asyncio
async def test_browse_markets_forwards_params() -> None:
    api = FakeApiClient()
    market = _market(ticker="MKT-1")
    api.browse_result = MarketPage(items=[market], next_cursor="next-page", limit=5)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "browse_markets",
            {"params": {"category": ["Politics"], "yes_ask_price_gte": 0.2, "limit": 5, "cursor": "abc"}},
        )
    assert len(api.browse_calls) == 1
    call = api.browse_calls[0]
    assert call.category == ["Politics"]
    assert call.yes_ask_price_gte == pytest.approx(0.2)
    assert call.limit == 5
    assert call.cursor == "abc"
    page = MarketPage.model_validate(result.structured_content)
    assert page.next_cursor == "next-page"
    assert page.items[0].ticker == "MKT-1"


@pytest.mark.asyncio
async def test_browse_markets_forwards_tags_mode() -> None:
    api = FakeApiClient()
    api.browse_result = MarketPage(items=[], next_cursor=None, limit=8)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        await client.call_tool(
            "browse_markets",
            {"params": {"tags": ["climate", "energy"], "tags_mode": "all"}},
        )
    assert api.browse_calls[0].tags == ["climate", "energy"]
    assert api.browse_calls[0].tags_mode == "all"


@pytest.mark.asyncio
async def test_browse_markets_defaults_limit() -> None:
    api = FakeApiClient()
    api.browse_result = MarketPage(items=[], next_cursor=None, limit=8)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        await client.call_tool("browse_markets", {"params": {}})
    assert len(api.browse_calls) == 1
    assert api.browse_calls[0].limit == 8


@pytest.mark.asyncio
async def test_browse_markets_rejects_limit_above_max() -> None:
    api = FakeApiClient()
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="20"):
            await client.call_tool("browse_markets", {"params": {"limit": 21}})
    assert api.browse_calls == []


@pytest.mark.asyncio
async def test_search_markets_forwards_query() -> None:
    api = FakeApiClient()
    market = _market(ticker="MKT-0")
    api.search_result = MarketPage(items=[market], next_cursor=None, limit=2)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_markets",
            {"params": {"q": "oil prices", "limit": 2, "tags": ["fed"]}},
        )
    assert api.search_calls[0].q == "oil prices"
    assert api.search_calls[0].tags == ["fed"]
    page = MarketPage.model_validate(result.structured_content)
    assert page.items[0].ticker == "MKT-0"
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_search_markets_forwards_tags_mode() -> None:
    api = FakeApiClient()
    market = _market(ticker="MKT-0")
    api.search_result = MarketPage(items=[market], next_cursor=None, limit=2)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        await client.call_tool(
            "search_markets",
            {"params": {"q": "oil", "tags": ["climate", "energy"], "tags_mode": "all"}},
        )
    assert api.search_calls[0].tags == ["climate", "energy"]
    assert api.search_calls[0].tags_mode == "all"


@pytest.mark.asyncio
async def test_list_categories_forwards() -> None:
    api = FakeApiClient()
    api.categories_result = VocabList(items=["Politics", "Economics"], truncated=False, limit=20)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        result = await client.call_tool("list_categories", {"params": {}})
    assert api.list_categories_calls[0].limit == 20
    vocab = VocabList.model_validate(result.structured_content)
    assert vocab.items == ["Politics", "Economics"]
    assert vocab.truncated is False
    assert vocab.limit == 20


@pytest.mark.asyncio
async def test_list_tags_forwards_limit() -> None:
    api = FakeApiClient()
    api.tags_result = VocabList(items=["elections", "fed"], truncated=True, limit=2)
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        result = await client.call_tool("list_tags", {"params": {"limit": 2}})
    assert api.list_tags_calls[0].limit == 2
    vocab = VocabList.model_validate(result.structured_content)
    assert vocab.items == ["elections", "fed"]
    assert vocab.truncated is True
    assert vocab.limit == 2


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
    assert event.market_count == 2


@pytest.mark.asyncio
async def test_get_market_missing_is_tool_error() -> None:
    api = FakeApiClient()
    api.errors["MISSING"] = OpenhedgeApiError(404, "market not found")
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match=r"404: market not found"):
            await client.call_tool("get_market", {"ticker": "MISSING"})


@pytest.mark.asyncio
async def test_search_unavailable_is_tool_error() -> None:
    api = FakeApiClient()
    api.errors["search"] = OpenhedgeApiError(503, "search is unavailable: embeddings are not configured")
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match=r"503: search is unavailable: embeddings are not configured"):
            await client.call_tool("search_markets", {"params": {"q": "oil"}})


@pytest.mark.asyncio
async def test_hedge_fetches_ticker_and_sizes() -> None:
    api = FakeApiClient()
    market = _market(ticker="MKT-0", yes_ask_price=0.4, yes_ask_size=1000.0)
    api.markets["MKT-0"] = market
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "hedge",
            {
                "ticker": "MKT-0",
                "side": "yes",
                "estimated_hit_dollars": 100,
                "coverage": 1.0,
            },
        )
    assert api.get_market_calls == ["MKT-0"]
    assert api.search_calls == []
    payload = result.structured_content
    assert payload is not None
    assert "market" not in payload
    assert "description" not in payload
    assert "candidates" not in payload
    candidate = HedgeCandidate.model_validate(payload)
    assert candidate.ticker == "MKT-0"
    assert candidate.url == market.url
    assert candidate.question == "Active market"
    assert candidate.side == "yes"
    assert candidate.contracts == pytest.approx(100.0)
    assert candidate.premium_dollars == pytest.approx(40.0)


@pytest.mark.asyncio
async def test_hedge_missing_ticker_is_tool_error() -> None:
    api = FakeApiClient()
    api.errors["MISSING"] = OpenhedgeApiError(404, "market not found")
    mcp = create_mcp(api_client=api)
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match=r"404: market not found"):
            await client.call_tool("hedge", {"ticker": "MISSING"})


@pytest.mark.asyncio
async def test_list_prompts_and_resources() -> None:
    mcp = create_mcp(api_client=FakeApiClient())
    async with Client(mcp) as client:
        prompts = await client.list_prompts()
        resources = await client.list_resources()
        prompt = await client.get_prompt("hedge_risk", {"risk": "diesel above $5"})
        resource = await client.read_resource("openhedge://docs/hedge-math")
    by_name = {item.name: item for item in prompts}
    assert "hedge_risk" in by_name
    assert by_name["hedge_risk"].description
    uris = {str(item.uri) for item in resources}
    assert "openhedge://docs/hedge-math" in uris
    prompt_text = "".join(getattr(message.content, "text", "") or "" for message in prompt.messages)
    assert "diesel above $5" in prompt_text
    assert "search_markets" in prompt_text.lower()
    assert "get_market" in prompt_text.lower()
    assert "none fits" in prompt_text.lower()
    assert "hedge" in prompt_text.lower()
    resource_text = "".join(block.text for block in resource)
    assert resource_text == HEDGE_MATH_MARKDOWN


@pytest.mark.asyncio
async def test_health_route() -> None:
    mcp = create_mcp(api_client=FakeApiClient())
    app = mcp.http_app(stateless_http=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_route_proxies_upstream() -> None:
    api = FakeApiClient()
    mcp = create_mcp(api_client=api)
    app = mcp.http_app(stateless_http=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "qdrant": "ok", "embedder": "ok"}


@pytest.mark.asyncio
async def test_ready_route_returns_upstream_error() -> None:
    api = FakeApiClient()
    api.errors["ready"] = OpenhedgeApiError(503, "not ready")
    mcp = create_mcp(api_client=api)
    app = mcp.http_app(stateless_http=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "not ready"}
