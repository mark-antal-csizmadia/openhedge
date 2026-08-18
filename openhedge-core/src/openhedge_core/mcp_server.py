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
from openhedge_core.hedge import HEDGE_MATH_MARKDOWN, HedgeParams, HedgeResult, size_hedges
from openhedge_core.server import MarketListParams, MarketPage, MarketSearchParams, TagSearchParams, VocabList
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

INSTRUCTIONS = """\
openhedge discovers hedges in event contracts and prediction markets. It does not place orders.

Workflow:
1. Use search_markets (try several queries or add filters) when the user describes an exposure in
   prose. Use browse_markets when they already have structured filters. Hits are compact:
   question, outcomes, prices/sizes, and url — not resolution rules. Use list_categories for the
   full set of category filter values. Use search_tags to discover tag filter values.
2. Use get_event when a strike ladder might fit. Compare question, yes_outcome/no_outcome,
   and strike_order. get_event is capped; if truncated is true, continue with browse_markets
   using event_ticker=[that ticker] and follow next_cursor. Browse is not strike-ordered and
   may overlap the returned slice — dedupe by ticker, then compare strike_order. Call
   get_market on shortlisted tickers and read description (resolution rules); drop poor
   proxies. If none map cleanly, say none fits.
3. Use hedge only after you have chosen tickers and read their rules via get_market. Pass
   legs as {ticker, side} plus optional estimated_hit_dollars. hedge fetches those markets
   and sizes a cash-flow hedge; it does not search. Link the user to each candidate's
   market.url.
4. Use get_market to fetch the full record for one ticker, including description.

Honesty: search returns nearest neighbors, not guaranteed hedges. State basis risk explicitly.
Read resource openhedge://docs/hedge-math for settlement, Yes/No complement, and sizing formulas.
The hedge_risk prompt is the playbook for collecting markets then sizing.

Pagination: browse_markets uses cursor pagination. If a page includes next_cursor, pass it back as
cursor for the next page. search_markets returns a single page; refine q or add filters instead of
paging. search_tags is also a single page of keyword matches; if nothing fits, try a different q
(for example fed, election) rather than paging. Matching is a substring on tag strings, not
semantic search. list_categories returns the full set; do not page it. get_event returns at most
50 markets ordered by strike_order. If truncated is true, continue with browse_markets using
event_ticker=[that ticker] and follow next_cursor. Browse is not strike-ordered and may overlap
the returned slice; dedupe by ticker, then compare strike_order.
Prices are in dollars in [0, 1]. yes_ask_price is the best YES sell offer; yes_bid_price is the best YES buy offer. A YES ask plus the corresponding NO bid equals 1.0. Compact hits include yes_ask_size and yes_bid_size.
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

    @mcp.tool(title="Hedge a risk", annotations=_READ_ONLY_TOOL)
    async def hedge(params: HedgeParams) -> HedgeResult:
        """Size event-contract hedges on markets you already chose.

        Use this after search_markets, browse_markets, or get_event, and after get_market
        on each ticker so you have read the resolution rules. Do not use this to look up markets.

        For each leg it fetches the ticker and sizes a buy of that side at the current best
        ask. Each candidate includes premium, gross $1 payout, residual P&L when a dollar hit
        is given, and whether top-of-book size capped the position. Legs are sized independently.
        It does not place orders; send the user to market.url.

        Args:
            params: Required `legs` (`ticker` plus `side`, default yes) and optional
                `estimated_hit_dollars` and `coverage`.

        Returns:
            Sizing inputs and a list of sized `candidates` in leg order.

        Raises:
            ToolError: If a ticker is missing (upstream 404) or `legs` is empty (422).
        """
        markets_and_sides = [(await _call_api(api_client.get_market, leg.ticker), leg.side) for leg in params.legs]
        return size_hedges(markets_and_sides, params)

    @mcp.tool(title="Browse markets", annotations=_READ_ONLY_TOOL)
    async def browse_markets(params: MarketListParams) -> MarketPage:
        """Browse markets with structured filters and cursor pagination.

        Use this when the user already knows filters such as category, tags, tickers, or price
        ranges, and does not need semantic search. Results are not ranked by relevance; each
        item's score is null. Hits are compact (question, outcomes, prices/sizes, url); call
        get_market for resolution rules.

        Args:
            params: Filters plus page size and optional cursor. Keyword list filters are OR'd
                within a field. Range filters (`*_gte` / `*_lte`) are inclusive. Pass
                `next_cursor` from the previous page as `cursor`. Omit `cursor` for the first page.

        Returns:
            A page of compact market hits (`items`, `next_cursor`, `limit`). Follow `next_cursor`
            until it is null.
        """
        return await _call_api(api_client.browse_markets, params)

    @mcp.tool(title="Search markets", annotations=_READ_ONLY_TOOL)
    async def search_markets(params: MarketSearchParams) -> MarketPage:
        """Semantically search markets for hedges matching a natural-language query.

        Prefer this over browse_markets when the user describes an exposure, event, or topic
        in prose. Hits are compact (question, outcomes, prices/sizes, url). Call get_market
        for resolution rules before keeping a proxy, then hedge with those tickers. The
        upstream API embeds `q` and ranks markets by similarity. Optional filters restrict
        the candidate set. This is a single page; refine `q` or add filters rather than paging.

        Args:
            params: Required `q` plus optional filters and `limit` (default 8, maximum 20).
                Do not page; refine `q` or add filters for more results.

        Returns:
            Compact market hits with similarity `score` on each. A single page; `next_cursor`
            is always null.

        Raises:
            ToolError: If embeddings are not configured (upstream 503) or `q` is empty (422).
        """
        return await _call_api(api_client.search_markets, params)

    @mcp.tool(title="Get a market", annotations=_READ_ONLY_TOOL)
    async def get_market(
        ticker: Annotated[str, Field(description="Market primary key, typically taken from a previous page item.")],
    ) -> Market:
        """Fetch one market by ticker.

        Use after search_markets, browse_markets, or get_event when you need the full record:
        question, resolution rules (`description`), yes/no outcomes, ask/bid prices and sizes,
        volume, and the canonical platform URL. List and event tools omit description. hedge
        fetches this itself for each sized leg.

        Args:
            ticker: Market primary key, typically taken from a previous page item.

        Returns:
            The full market record.

        Raises:
            ToolError: If no market exists for `ticker` (upstream 404).
        """
        return await _call_api(api_client.get_market, ticker)

    @mcp.tool(title="Get an event", annotations=_READ_ONLY_TOOL)
    async def get_event(
        event_ticker: Annotated[
            str,
            Field(description="Event primary key, typically event_ticker from a market record."),
        ],
    ) -> Event:
        """Fetch an event and its markets, ordered by strike_order and capped.

        Use when comparing related contracts in the same event (for example a ladder of strikes).
        Markets are compact (question, outcomes, prices/sizes, strike_order); call get_market
        for resolution rules on shortlisted tickers. At most 50 markets are returned. If
        truncated is true, continue with browse_markets using event_ticker=[that ticker] and
        follow next_cursor. Browse is not strike-ordered and may overlap the returned slice;
        dedupe by ticker, then compare strike_order.

        Args:
            event_ticker: Event primary key, typically `event_ticker` from a market record.

        Returns:
            The event with compact `markets` sorted by `strike_order`. `market_count` is the
            total before capping. If `truncated` is true, more markets exist.

        Raises:
            ToolError: If no markets exist for `event_ticker` (upstream 404).
        """
        return await _call_api(api_client.get_event, event_ticker)

    @mcp.tool(title="List categories", annotations=_READ_ONLY_TOOL)
    async def list_categories() -> VocabList:
        """List every market category value currently in the catalog.

        Use this to discover valid `category` filter values before browse_markets or
        search_markets. The list is complete; do not page it. Pass items into `category`
        as a list.

        Returns:
            `items` is the full set of category strings, sorted alphabetically.
        """
        return await _call_api(api_client.list_categories)

    @mcp.tool(title="Search tags", annotations=_READ_ONLY_TOOL)
    async def search_tags(params: TagSearchParams) -> VocabList:
        """Find tag filter values by keyword substring.

        Use this to discover valid `tags` filter values before browse_markets or
        search_markets. Matching is a case-insensitive substring on tag strings, not
        semantic search. This is a single page; if nothing fits, try a different `q`
        (for example fed, election) rather than paging.

        Args:
            params: Required `q` plus optional `limit` (default 20, maximum 50).

        Returns:
            Matching tag strings in `items`. A single page; do not request a cursor.

        Raises:
            ToolError: If `q` is empty (422).
        """
        return await _call_api(api_client.search_tags, params)

    @mcp.prompt
    def hedge_risk(risk: str) -> str:
        """Playbook for collecting markets, then sizing a hedge.

        Use this when a user asks to hedge a real-world risk. It tells the agent to search
        first, keep only clean proxies, then call hedge with those tickers.
        """
        return (
            f"The user wants to hedge this exposure:\n\n{risk}\n\n"
            "1. Discover markets with search_markets (try several queries or add filters). "
            "Use browse_markets for structured filters. If a strike ladder might fit, call "
            "get_event and compare markets by strike_order. Those results are compact and "
            "capped; if truncated, continue with browse_markets using event_ticker.\n"
            "2. Call get_market on shortlisted tickers. Read question, yes_outcome/no_outcome, "
            "and description (resolution rules). Keep only clean proxies. State basis risk "
            "explicitly. Do not force a match; if none fits, stop and say so. Do not call "
            "hedge yet.\n"
            "3. Call hedge with legs as {{ticker, side}} for the kept markets. Default side "
            "is yes; use no when that market's NO resolution is the hedge. If they gave a "
            "dollar loss, pass estimated_hit_dollars.\n"
            "4. Present premium_dollars, gross_payout_dollars, and residual "
            "(net_if_pays / net_if_expires). Flag liquidity_constrained positions. Legs are "
            "sized independently; overlapping contracts can overstate coverage.\n"
            "5. Link market.url. openhedge does not execute trades.\n"
            "Read resource openhedge://docs/hedge-math if you need the settlement formulas."
        )

    @mcp.resource("openhedge://docs/hedge-math")
    def hedge_math() -> str:
        """Binary settlement, Yes/No complement, and how the hedge tool sizes positions."""
        return HEDGE_MATH_MARKDOWN

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
