import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from openhedge_core.api_client import MarketApi, OpenhedgeApiClient, OpenhedgeApiError
from openhedge_core.server import MAX_SEARCH_OFFSET, MarketListParams, MarketPage, MarketSearchParams
from openhedge_core.types.market import Event, Market

T = TypeVar("T")

DEFAULT_OPENHEDGE_API_URL = "http://127.0.0.1:8000"
DEFAULT_MCP_HOST = "0.0.0.0"
DEFAULT_MCP_PORT = 8001

logger = logging.getLogger(__name__)

_READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    openWorldHint=True,
)

INSTRUCTIONS = f"""\
openhedge discovers hedges in event contracts and prediction markets.

Workflow:
1. Use search_markets when the user describes an exposure or topic in natural language.
2. Use browse_markets when the user already has structured filters (category, tags, prices, tickers).
3. Use get_market once you have a market ticker and need the full record (rules, prices, URL).
4. Use get_event once you have an event_ticker to see every related market, ordered by strike_order.

Pagination: if a page includes next_cursor, pass it back as cursor for the next page. Search cursors
are numeric offsets and cannot exceed {MAX_SEARCH_OFFSET}.
Prices are probabilities in [0, 1]; price_yes + price_no is approximately 1.
Keyword filters are lists (OR within a field). Range filters are inclusive.
search_markets requires embeddings on the upstream API and fails if they are not configured.
"""


def create_mcp(*, api_client: MarketApi, close_client: bool = False) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[None]:
        yield
        if close_client and isinstance(api_client, OpenhedgeApiClient):
            await api_client.aclose()

    mcp = FastMCP("openhedge", instructions=INSTRUCTIONS, lifespan=lifespan)

    @mcp.tool(annotations=_READ_ONLY_TOOL)
    async def browse_markets(params: MarketListParams) -> MarketPage:
        """Browse markets with structured filters and cursor pagination.

        Use this when the user already knows filters such as category, tags, tickers, or price
        ranges, and does not need semantic search. Results are not ranked by relevance; each
        item's score is null.

        Args:
            params: Filters plus page size and optional cursor. Keyword list filters are OR'd
                within a field. Range filters (`*_gte` / `*_lte`) are inclusive. Pass
                `next_cursor` from the previous page as `cursor`. Omit `cursor` for the first page.

        Returns:
            A page of markets (`items`, `next_cursor`, `limit`). Follow `next_cursor` until it is null.
        """
        return await _call_api(api_client.browse_markets, params)

    @mcp.tool(annotations=_READ_ONLY_TOOL)
    async def search_markets(params: MarketSearchParams) -> MarketPage:
        """Semantically search markets for hedges matching a natural-language query.

        Prefer this over browse_markets when the user describes an exposure, event, or topic
        in prose. The upstream API embeds `q` and ranks markets by similarity. Optional filters
        restrict the candidate set.

        Args:
            params: Required `q` plus the same filters and pagination as browse_markets.
                Search `cursor` is a numeric offset from `next_cursor`. The offset plus `limit`
                must not exceed the maximum search offset.

        Returns:
            A page of markets with similarity `score` on each hit. Follow `next_cursor` until it is null.

        Raises:
            ToolError: If embeddings are not configured (upstream 503), `q` is empty (422),
                or `cursor` is invalid or past the maximum offset (400).
        """
        return await _call_api(api_client.search_markets, params)

    @mcp.tool(annotations=_READ_ONLY_TOOL)
    async def get_market(
        ticker: Annotated[str, Field(description="Market primary key, typically taken from a previous page item.")],
    ) -> Market:
        """Fetch one market by ticker.

        Use after search_markets or browse_markets when you need the full record: question,
        resolution rules, yes/no outcomes and prices, volume, and the canonical platform URL.

        Args:
            ticker: Market primary key, typically taken from a previous page item.

        Returns:
            The full market record.

        Raises:
            ToolError: If no market exists for `ticker` (upstream 404).
        """
        return await _call_api(api_client.get_market, ticker)

    @mcp.tool(annotations=_READ_ONLY_TOOL)
    async def get_event(
        event_ticker: Annotated[
            str,
            Field(description="Event primary key, typically event_ticker from a market record."),
        ],
    ) -> Event:
        """Fetch an event and all of its markets, ordered by strike_order.

        Use when comparing related contracts in the same event (for example a ladder of strikes).

        Args:
            event_ticker: Event primary key, typically `event_ticker` from a market record.

        Returns:
            The event with `markets` sorted by `strike_order`.

        Raises:
            ToolError: If no markets exist for `event_ticker` (upstream 404).
        """
        return await _call_api(api_client.get_event, event_ticker)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return mcp


async def _call_api(method: Callable[..., Awaitable[T]], *args: object) -> T:
    try:
        return await method(*args)
    except OpenhedgeApiError as exc:
        raise ToolError(exc.detail) from exc


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    base_url = os.environ.get("OPENHEDGE_API_URL", DEFAULT_OPENHEDGE_API_URL)
    api_client = OpenhedgeApiClient.from_base_url(base_url)
    mcp = create_mcp(api_client=api_client, close_client=True)
    logger.info("MCP proxying %s", base_url)
    mcp.run(
        transport="http",
        host=os.environ.get("MCP_HOST", DEFAULT_MCP_HOST),
        port=int(os.environ.get("MCP_PORT", str(DEFAULT_MCP_PORT))),
        path="/mcp",
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
