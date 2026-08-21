import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Literal, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from openhedge_core.api_client import MarketApi, OpenhedgeApiClient, OpenhedgeApiError
from openhedge_core.hedge import (
    HEDGE_MATH_MARKDOWN,
    HedgeCandidate,
    HedgeCard,
    HedgeCardParams,
    HedgeParams,
    HedgeSide,
    HedgeVerdict,
    compose_hedge_card,
    size_hedge,
)
from openhedge_core.server import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    MAX_PAGE_LIMIT,
    MAX_SEARCH_LIMIT,
    MarketListParams,
    MarketPage,
    MarketSearchParams,
    VocabList,
    VocabListParams,
)
from openhedge_core.settings import McpServerSettings
from openhedge_core.types.market import Event, Market

T = TypeVar("T")

logger = logging.getLogger(__name__)

_READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    openWorldHint=True,
)

INSTRUCTIONS = """\
openhedge discovers hedges in event contracts and prediction markets. It does not place orders.

Honesty: search returns nearest neighbors, not hedges. Do not force a fit. If question, outcomes,
or resolution rules do not map cleanly to the user's exposure, do not call hedge. Call
present_hedge with verdict=none and no candidate. An honest gap is the correct result; do not
pick the least-bad neighbor. State basis risk explicitly.

Workflow:
1. Use search_markets (try several queries or add filters) when the user describes an exposure in
   prose. Use browse_markets when they already have structured filters. Hits are compact:
   question, outcomes, prices/sizes, end_datetime, and url — not resolution rules.
   The catalog is meant to be open markets; check end_datetime. Judge relevance from those
   fields; drop poor proxies.
   Use list_categories and list_tags for the most popular filter values, not a complete catalog.
   search_markets and browse_markets accept category, tags, tags_mode, end_datetime_gte/lte, and
   yes_ask_price_gte/lte. browse_markets also accepts event_ticker. Use get_market or get_event
   for tickers. Judge liquidity from compact hit sizes and hedge.liquidity_constrained; do not
   filter by size or volume.
2. Use get_event when a strike ladder might fit. It returns all markets for that event,
   ordered by strike_order. Compare question, yes_outcome/no_outcome, and strike_order.
   Call get_market on shortlisted tickers and read description (resolution rules); drop poor
   proxies. If none map cleanly, do not call hedge; use present_hedge with verdict=none.
3. Use hedge only after you have chosen tickers and read their rules via get_market. Call
   hedge once per kept ticker with that ticker, side, and optional estimated_hit_dollars.
   You may call hedge in parallel. hedge fetches that market and sizes a cash-flow hedge;
   it does not search. Read target versus filled size from the candidate
   (target_payout_dollars, unconstrained_contracts, coverage_achieved, unhedged_hit_dollars);
   do not reconstruct them. If none map cleanly, do not call hedge.
4. Use present_hedge as the last step. For a kept ticker, pass the unmodified hedge payload
   as candidate with verdict=fit, plus headline, why_this_pays, and basis_risk. If none fits, call
   present_hedge with verdict=none and no candidate (omit why_this_pays). Paste markdown as the
   user reply; do not restate dollars in different figures.
5. Use get_market to fetch the full record for one ticker, including description.

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


class McpDiscoveryFilters(BaseModel):
    """Hedge-oriented subset of REST MarketFilters for MCP browse and search."""

    model_config = ConfigDict(extra="forbid")
    category: list[str] | None = Field(
        default=None,
        description="Market categories to include (for example Politics). Multiple values are OR'd.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Tags to include. Combined with `tags_mode` (default OR).",
    )
    tags_mode: Literal["any", "all"] = Field(
        default="any",
        description="How multiple tags are combined. `any` ORs them; `all` requires every tag.",
    )
    end_datetime_gte: AwareDatetime | None = Field(
        default=None,
        description="Inclusive lower bound on market end datetime (timezone-aware ISO-8601).",
    )
    end_datetime_lte: AwareDatetime | None = Field(
        default=None,
        description="Inclusive upper bound on market end datetime (timezone-aware ISO-8601).",
    )
    yes_ask_price_gte: float | None = Field(
        default=None,
        description="Inclusive lower bound on the best YES ask price in dollars. Prices are in [0, 1]; a YES ask plus the corresponding NO bid equals 1.0.",
    )
    yes_ask_price_lte: float | None = Field(
        default=None,
        description="Inclusive upper bound on the best YES ask price in dollars. Prices are in [0, 1]; a YES ask plus the corresponding NO bid equals 1.0.",
    )


class McpBrowseParams(McpDiscoveryFilters):
    event_ticker: list[str] | None = Field(
        default=None,
        description="Event tickers to include. Multiple values are OR'd.",
    )
    limit: int = Field(
        default=DEFAULT_PAGE_LIMIT,
        ge=1,
        le=MAX_PAGE_LIMIT,
        description="Page size. Defaults to 8, maximum 20.",
    )
    cursor: str | None = Field(
        default=None,
        description="Pagination cursor from the previous page's next_cursor. Omit for the first page.",
    )


class McpSearchParams(McpDiscoveryFilters):
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
                    "(contracts sized for $1 of payout) without signed P&L."
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

        It fetches the ticker and sizes a buy of that side at the current best ask only
        (no deeper book / VWAP). The candidate includes premium (fees omitted), gross $1
        payout, signed P&L when a dollar hit is given, unhedged leftover hit, and whether
        top-of-book size capped the position. Calls are sized independently. It does not place orders;
        send the user to url.

        Args:
            ticker: Market primary key.
            side: Side to buy; default yes.
            estimated_hit_dollars: Optional modeled dollar loss.
            coverage: Fraction of the hit to target; default 1.0.

        Returns:
            One sized candidate (`ticker`, `url`, `question`, sizing numbers, and echoes of
            estimated_hit_dollars, coverage, target_payout_dollars, unconstrained_contracts,
            coverage_achieved, unhedged_hit_dollars).

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

    @mcp.tool(title="Present a hedge card", annotations=_READ_ONLY_TOOL)
    async def present_hedge(
        verdict: Annotated[
            HedgeVerdict,
            Field(description="fit when a sized candidate is kept; none when no market maps cleanly."),
        ],
        headline: Annotated[str, Field(min_length=1, description="Restated user exposure in one line.")],
        basis_risk: Annotated[
            str,
            Field(
                min_length=1,
                description="Why this market is a proxy (or why none fits). Do not put dollar figures here.",
            ),
        ],
        why_this_pays: Annotated[
            str | None,
            Field(
                min_length=1,
                description=(
                    "Why this market pays when the exposure hits. Required for fit; omit for none. "
                    "Do not put dollar figures here."
                ),
            ),
        ] = None,
        candidate: Annotated[
            HedgeCandidate | None,
            Field(description="Unmodified hedge tool result. Required for fit; omit for none."),
        ] = None,
        other_exposures: Annotated[
            list[str] | None,
            Field(description="Optional related risks noticed but not sized on this card."),
        ] = None,
    ) -> HedgeCard:
        """Format a prior hedge result as the user-facing card.

        Call hedge first for each kept ticker, then present_hedge once per ticker with
        verdict=fit. Pass the hedge tool result unmodified as candidate; do not round or
        invent dollar fields. If none fits, skip hedge and call present_hedge with
        verdict=none and no candidate (omit why_this_pays). Paste markdown as the user
        reply; do not restate dollars in different figures. This tool does not fetch or
        re-size.

        Args:
            verdict: fit or none.
            headline: Restated user exposure.
            why_this_pays: Why this market pays when the exposure hits; required for fit.
            basis_risk: Proxy caveat, or why none fits.
            candidate: Unmodified hedge payload; required for fit.
            other_exposures: Optional related risks not sized here.

        Returns:
            A card with the inbound candidate (null when none) and frozen markdown.

        Raises:
            ToolError: If verdict=fit is missing candidate or why_this_pays, or
                verdict=none includes either.
        """
        try:
            params = HedgeCardParams(
                verdict=verdict,
                headline=headline,
                why_this_pays=why_this_pays,
                basis_risk=basis_risk,
                candidate=candidate,
                other_exposures=other_exposures or [],
            )
        except ValidationError as exc:
            raise ToolError(str(exc)) from exc
        return compose_hedge_card(params)

    @mcp.tool(title="Browse markets", annotations=_READ_ONLY_TOOL)
    async def browse_markets(params: McpBrowseParams) -> MarketPage:
        """Browse markets with structured filters and cursor pagination.

        Use this when the user already knows filters such as category, tags, event_ticker,
        end_datetime, or YES ask price, and does not need semantic search. Results are not
        ranked by relevance. Hits are compact (question, outcomes, prices/sizes, end_datetime,
        url); call get_market for resolution rules. The catalog is meant to be open markets;
        check end_datetime.

        Args:
            params: Filters plus page size (default 8, maximum 20) and optional cursor. Allowed
                filters: category, tags, tags_mode, event_ticker, end_datetime_gte/lte,
                yes_ask_price_gte/lte. Keyword list filters are OR'd within a field; pass
                `tags_mode=all` to require every tag. Range filters (`*_gte` / `*_lte`) are
                inclusive. Pass `next_cursor` from the previous page as `cursor`. Omit `cursor`
                for the first page. Use get_market or get_event for tickers; judge liquidity
                from hit sizes and hedge.liquidity_constrained.

        Returns:
            A page of compact market hits (`items`, `next_cursor`, `limit`). Follow `next_cursor`
            until it is null.
        """
        return await _call_api(
            api_client.browse_markets,
            MarketListParams.model_validate(params.model_dump()),
        )

    @mcp.tool(title="Search markets", annotations=_READ_ONLY_TOOL)
    async def search_markets(params: McpSearchParams) -> MarketPage:
        """Semantically search markets for hedges matching a natural-language query.

        Prefer this over browse_markets when the user describes an exposure, event, or topic
        in prose. Hits are compact (question, outcomes, prices/sizes, end_datetime, url). Call
        get_market for resolution rules before keeping a proxy, then hedge with those tickers.
        The upstream API embeds `q` and returns nearest neighbors. Optional filters restrict
        the candidate set: category, tags, tags_mode, end_datetime_gte/lte, yes_ask_price_gte/lte.
        The catalog is meant to be open markets; check end_datetime. Judge relevance from
        question, outcomes, prices, and end_datetime; drop poor proxies. This is a single page;
        refine `q` or add filters rather than paging.

        Args:
            params: Required `q` plus optional filters and `limit` (default 8, maximum 20).
                Keyword list filters are OR'd within a field; pass `tags_mode=all` to require
                every tag. Do not page; refine `q` or add filters for more results. Use
                get_market or get_event for tickers; judge liquidity from hit sizes and
                hedge.liquidity_constrained.

        Returns:
            Compact market hits, nearest neighbors first. A single page; `next_cursor` is
            always null.

        Raises:
            ToolError: If embeddings are not configured (upstream 503) or `q` is empty (422).
        """
        return await _call_api(
            api_client.search_markets,
            MarketSearchParams.model_validate(params.model_dump()),
        )

    @mcp.tool(title="Get a market", annotations=_READ_ONLY_TOOL)
    async def get_market(
        ticker: Annotated[str, Field(description="Market primary key, typically taken from a previous page item.")],
    ) -> Market:
        """Fetch one market by ticker.

        Use after search_markets, browse_markets, or get_event when you need the full record:
        question, resolution rules (`description`), yes/no outcomes, ask/bid prices and sizes,
        volume, and the canonical platform URL. List and event tools omit description.
        The catalog is meant to be open markets; check end_datetime.

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
        for resolution rules on shortlisted tickers. The catalog is meant to be open markets;
        check end_datetime.

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
        first, keep only clean proxies, then call hedge and present_hedge.
        """
        return (
            f"The user wants to hedge this exposure:\n\n{risk}\n\n"
            "1. Discover markets with search_markets (try several queries or add filters). "
            "Use browse_markets for structured filters. If a strike ladder might fit, call "
            "get_event and compare all markets by strike_order.\n"
            "2. Call get_market on shortlisted tickers. Read question, yes_outcome/no_outcome, "
            "and description (resolution rules). Keep only clean proxies. State basis risk "
            "explicitly. Do not force a fit. If none maps cleanly, do not call hedge. Call "
            "present_hedge with verdict=none (no candidate) and paste markdown. verdict=none "
            "is success.\n"
            "3. Call hedge once per kept ticker. Default side is yes; use no when that "
            "market's NO resolution is the hedge. If they gave a dollar loss, pass the same "
            "estimated_hit_dollars on each call. You may call hedge in parallel. Read "
            "target_payout_dollars, unconstrained_contracts, coverage_achieved, and "
            "unhedged_hit_dollars; do not reconstruct them.\n"
            "4. Call present_hedge once per kept ticker with verdict=fit. Pass the hedge "
            "tool result unmodified as candidate, plus headline, why_this_pays, and "
            "basis_risk. Paste markdown as the user reply; do not restate dollars in "
            "different figures. Calls are sized independently; overlapping contracts can "
            "overstate coverage.\n"
            "5. openhedge does not execute trades.\n"
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
    settings = McpServerSettings()
    api_client = OpenhedgeApiClient.from_base_url(settings.api_url)
    mcp = create_mcp(api_client=api_client, close_client=True)
    logger.info("MCP proxying %s", settings.api_url)
    mcp.run(
        transport="http",
        host=settings.host,
        port=settings.port,
        path="/mcp",
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
