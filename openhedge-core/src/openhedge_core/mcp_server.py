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
from openhedge_core.hedge import HEDGE_MATH_MARKDOWN, HedgeCandidate, HedgeParams, HedgeSide, size_hedge
from openhedge_core.server import MarketListParams, MarketPage, MarketSearchParams, VocabList, VocabListParams
from openhedge_core.types.market import Event, Market

T = TypeVar("T")

DEFAULT_OPENHEDGE_API_URL = "http://127.0.0.1:8000"
DEFAULT_MCP_HOST = "127.0.0.1"
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
   question, outcomes, prices/sizes, end_datetime, and url — not resolution rules.
   All returned markets are open. Judge relevance from those fields; drop poor proxies.
   Use list_categories and list_tags for the most popular filter values, not a complete catalog.
2. Use get_event when a strike ladder might fit. It returns all markets for that event,
   ordered by strike_order. Compare question, yes_outcome/no_outcome, and strike_order.
   Call get_market on shortlisted tickers and read description (resolution rules); drop poor
   proxies. If none map cleanly, say none fits.
3. Use hedge only after you have chosen tickers and read their rules via get_market. Call
   hedge once per kept ticker with that ticker, side, and optional estimated_hit_dollars.
   You may call hedge in parallel. hedge fetches that market and sizes a cash-flow hedge;
   it does not search. Link the user to each candidate's url.
4. Use get_market to fetch the full record for one ticker, including description.

Honesty: search returns nearest neighbors, not guaranteed hedges. State basis risk explicitly.
Read resource openhedge://docs/hedge-math for settlement, Yes/No complement, and sizing formulas.
The hedge_risk prompt is the playbook for collecting markets then sizing.

Pagination: browse_markets uses cursor pagination. If a page includes next_cursor, pass it back as
cursor for the next page. browse_markets page size defaults to 8 (maximum 20). search_markets
returns a single page; refine q or add filters instead of paging. list_categories and list_tags
return a single capped list of the most popular values, ordered by frequency. If truncated is true,
raise limit (maximum 100); do not page, and do not expect rare tags. get_event returns all markets
for the event, ordered by strike_order.
Prices are in dollars in [0, 1]. yes_ask_price is the best YES sell offer; yes_bid_price is the best YES buy offer. A YES ask plus the corresponding NO bid equals 1.0. Compact hits include yes_ask_size and yes_bid_size.
Keyword filters are lists (OR within a field). Pass tags_mode=all to require every tag.
Range filters are inclusive.
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
    async def hedge(
        ticker: Annotated[
            str,
            Field(
                min_length=1,
                description="Market primary key from search_markets, browse_markets, or get_event.",
            ),
        ],
        side: Annotated[
            HedgeSide,
            Field(
                description=(
                    "Contract side to buy: the side that pays $1 if the adverse outcome occurs. "
                    "Default yes. Use no when this market's NO resolution is the hedge."
                ),
            ),
        ] = "yes",
        estimated_hit_dollars: Annotated[
            float | None,
            Field(
                gt=0,
                description=(
                    "Modeled dollar loss if the adverse event happens. Omit to get unit economics "
                    "(contracts sized for $1 of payout) without residual P&L."
                ),
            ),
        ] = None,
        coverage: Annotated[
            float,
            Field(
                gt=0,
                le=1,
                description=(
                    "Fraction of estimated_hit_dollars to target as gross Kalshi payout. "
                    "Ignored for the target when no hit is given. Defaults to 1.0 (full offset)."
                ),
            ),
        ] = 1.0,
    ) -> HedgeCandidate:
        """Size an event-contract hedge on one market you already chose.

        Use this after search_markets, browse_markets, or get_event, and after get_market
        on this ticker so you have read the resolution rules. Do not use this to look up
        markets. Call once per kept ticker; you may call hedge in parallel.

        It fetches the ticker and sizes a buy of that side at the current best ask. The
        candidate includes premium, gross $1 payout, residual P&L when a dollar hit is
        given, and whether top-of-book size capped the position. Calls are sized
        independently. It does not place orders; send the user to url.

        Args:
            ticker: Market primary key.
            side: Side to buy; default yes.
            estimated_hit_dollars: Optional modeled dollar loss.
            coverage: Fraction of the hit to target; default 1.0.

        Returns:
            One sized candidate (`ticker`, `url`, `question`, and sizing numbers).

        Raises:
            ToolError: If the ticker is missing (upstream 404).
        """
        params = HedgeParams(
            ticker=ticker,
            side=side,
            estimated_hit_dollars=estimated_hit_dollars,
            coverage=coverage,
        )
        market = await _call_api(api_client.get_market, params.ticker)
        return size_hedge(market, params)

    @mcp.tool(title="Browse markets", annotations=_READ_ONLY_TOOL)
    async def browse_markets(params: MarketListParams) -> MarketPage:
        """Browse markets with structured filters and cursor pagination.

        Use this when the user already knows filters such as category, tags, tickers, or price
        ranges, and does not need semantic search. Results are not ranked by relevance. Hits are
        compact (question, outcomes, prices/sizes, end_datetime, url); call get_market for
        resolution rules. All returned markets are open.

        Args:
            params: Filters plus page size (default 8, maximum 20) and optional cursor. Keyword
                list filters are OR'd within a field; pass `tags_mode=all` to require every tag.
                Range filters (`*_gte` / `*_lte`) are inclusive. Pass `next_cursor` from the
                previous page as `cursor`. Omit `cursor` for the first page.

        Returns:
            A page of compact market hits (`items`, `next_cursor`, `limit`). Follow `next_cursor`
            until it is null.
        """
        return await _call_api(api_client.browse_markets, params)

    @mcp.tool(title="Search markets", annotations=_READ_ONLY_TOOL)
    async def search_markets(params: MarketSearchParams) -> MarketPage:
        """Semantically search markets for hedges matching a natural-language query.

        Prefer this over browse_markets when the user describes an exposure, event, or topic
        in prose. Hits are compact (question, outcomes, prices/sizes, end_datetime, url). Call
        get_market for resolution rules before keeping a proxy, then hedge with those tickers.
        The upstream API embeds `q` and returns nearest neighbors. Optional filters restrict
        the candidate set. All returned markets are open. Judge relevance from question,
        outcomes, prices, and end_datetime; drop poor proxies. This is a single page; refine
        `q` or add filters rather than paging.

        Args:
            params: Required `q` plus optional filters and `limit` (default 8, maximum 20).
                Keyword list filters are OR'd within a field; pass `tags_mode=all` to require
                every tag. Do not page; refine `q` or add filters for more results.

        Returns:
            Compact market hits, nearest neighbors first. A single page; `next_cursor` is
            always null.

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
        volume, and the canonical platform URL. List and event tools omit description.

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
        """Fetch an event and all of its markets, ordered by strike_order.

        Use when comparing related contracts in the same event (for example a ladder of strikes).
        Markets are compact (question, outcomes, prices/sizes, strike_order); call get_market
        for resolution rules on shortlisted tickers.

        Args:
            event_ticker: Event primary key, typically `event_ticker` from a market record.

        Returns:
            The event with all compact `markets` sorted by `strike_order`. `market_count` is
            the number of markets in the event.

        Raises:
            ToolError: If no markets exist for `event_ticker` (upstream 404).
        """
        return await _call_api(api_client.get_event, event_ticker)

    @mcp.tool(title="List categories", annotations=_READ_ONLY_TOOL)
    async def list_categories(params: VocabListParams) -> VocabList:
        """List the most popular market category values.

        Use this to discover valid `category` filter values before browse_markets or
        search_markets. Values are ordered by frequency, not alphabetically. The list is
        capped; if truncated is true, raise limit (maximum 100). Do not page. Pass items
        into `category` as a list. This is not a complete catalog.

        Args:
            params: Optional `limit` (default 20, maximum 100).

        Returns:
            Popular category strings in `items`. If `truncated` is true, more values exist.
        """
        return await _call_api(api_client.list_categories, params)

    @mcp.tool(title="List tags", annotations=_READ_ONLY_TOOL)
    async def list_tags(params: VocabListParams) -> VocabList:
        """List the most popular tag filter values.

        Use this to discover valid `tags` filter values before browse_markets or
        search_markets. Values are ordered by frequency. The list is capped; if truncated
        is true, raise limit (maximum 100). Do not page, and do not expect rare tags.
        Pass items into `tags` as a list. This is not a complete catalog.

        Args:
            params: Optional `limit` (default 20, maximum 100).

        Returns:
            Popular tag strings in `items`. If `truncated` is true, more values exist.
        """
        return await _call_api(api_client.list_tags, params)

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
            "get_event and compare all markets by strike_order.\n"
            "2. Call get_market on shortlisted tickers. Read question, yes_outcome/no_outcome, "
            "and description (resolution rules). Keep only clean proxies. State basis risk "
            "explicitly. Do not force a match; if none fits, stop and say so. Do not call "
            "hedge yet.\n"
            "3. Call hedge once per kept ticker. Default side is yes; use no when that "
            "market's NO resolution is the hedge. If they gave a dollar loss, pass the same "
            "estimated_hit_dollars on each call. You may call hedge in parallel.\n"
            "4. Present premium_dollars, gross_payout_dollars, and residual "
            "(net_if_pays / net_if_expires). Flag liquidity_constrained positions. Calls are "
            "sized independently; overlapping contracts can overstate coverage.\n"
            "5. Link url. openhedge does not execute trades.\n"
            "Read resource openhedge://docs/hedge-math if you need the settlement formulas."
        )

    @mcp.resource("openhedge://docs/hedge-math")
    def hedge_math() -> str:
        """Binary settlement, Yes/No complement, and how the hedge tool sizes positions."""
        return HEDGE_MATH_MARKDOWN

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @mcp.custom_route("/ready", methods=["GET"])
    async def ready(_request: Request) -> JSONResponse:
        try:
            status = await api_client.ready()
        except OpenhedgeApiError as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return JSONResponse(status.model_dump())

    return mcp


async def _call_api(method: Callable[..., Awaitable[T]], *args: object) -> T:
    try:
        return await method(*args)
    except OpenhedgeApiError as exc:
        raise ToolError(str(exc)) from exc


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
