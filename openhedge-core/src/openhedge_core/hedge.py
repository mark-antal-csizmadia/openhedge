from typing import Literal, Self

from jinja2 import Environment, PackageLoader
from pydantic import BaseModel, ConfigDict, Field, model_validator

from openhedge_core.types.market import PRICE_DECIMALS, Market, MarketSource

HedgeSide = Literal["yes", "no"]
HedgeVerdict = Literal["fit", "none"]

CONTRACT_PRECISION = 2
COVERAGE_ACHIEVED_DECIMALS = 4
UNIT_PAYOUT_DOLLARS = 1.0

HEDGE_MATH_MARKDOWN = """\
# openhedge hedge math

Only **binary** event contracts are supported for now; the catalog does not ingest scalar
markets. A binary contract on the chosen side pays **$1.00** if that side resolves and
**$0.00** otherwise. Prices are in dollars in `[0, 1]` and are not snapped to cents
(deci-cent books quote to 0.001). Contract counts snap to 0.01.

## Yes / No complement

The book is one pool viewed from two sides:

- YES ask + NO bid = 1.00
- YES bid + NO ask = 1.00
- Size at the YES ask equals size at the complementary NO bid
- Size at the YES bid equals size at the complementary NO ask

Buying YES at price `P` is the same exposure as selling NO at `1 - P`. Kalshi still charges
a trade fee (plus rounding); `hedge` ignores fees, so premium and `net_if_*` are slightly
optimistic versus a real fill.

## How `hedge` sizes a position

Discovery is not part of this tool. The agent chooses markets with `search_markets`,
`browse_markets`, and `get_event`, then calls `hedge` once per ticker. `hedge` fetches that
ticker and sizes a **buy** of that side at the current best ask (not a custom limit price).
Agents may call `hedge` in parallel for several tickers.

Kalshi's orderbook is bids-only (`yes_dollars` / `no_dollars` ladders); a YES ask is the
complement of the best NO bid. `hedge` uses the stored top of that book only. It does not
fetch the orderbook endpoint or walk deeper levels for a VWAP premium.

- YES: `price = yes_ask_price`, `available_size = yes_ask_size`
- NO: `price = 1 - yes_bid_price`, `available_size = yes_bid_size`

If `estimated_hit_dollars` is set:

- `target_payout = estimated_hit_dollars * coverage`
- `contracts = min(round(target_payout, 2), available_size)`
- `premium = contracts * price` (quoted ask only; no fees)
- `gross_payout = contracts` (each contract pays $1)
- `net_if_pays = estimated_hit_dollars - gross_payout - premium`
- `net_if_expires = -premium`

The candidate echoes `estimated_hit_dollars`, requested `coverage`, `target_payout_dollars`
(unconstrained gross target), and `unconstrained_contracts` (that target before the book
cap). `coverage_achieved` is `gross_payout_dollars / estimated_hit_dollars` when a hit was
given (null for unit economics). It is payout versus modeled loss, not versus requested
`coverage`. Read target versus filled size from those fields; do not reconstruct them.

Each call is sized independently against the full hit. Overlapping contracts (same event,
several strikes) can overstate coverage.

If no dollar hit is given, the same formulas run with `target_payout = $1` (unit economics)
and `net_if_pays` / `net_if_expires` are omitted.

`liquidity_constrained` is true when top-of-book size is smaller than the unconstrained
contract count. Size is capped at that quoted ask; `hedge` does not fill remaining size
at worse prices. That is a warning, not a reason to invent size beyond the quoted ask.

## When to say none fits

Reject a candidate when `question`, `yes_outcome` / `no_outcome`, or `description`
(resolution rules) do not map cleanly to the user's exposure. List, search, and event
hits are compact and omit `description`, `can_close_early`, and `early_close_condition`;
fetch those with `get_market` before keeping a proxy. `end_datetime` is the scheduled
close. If `can_close_early` is true, trading can stop earlier when
`early_close_condition` is met; keep the market only if that still covers the user's
exposure window. Prefer an honest gap over a forced proxy. Basis risk (for example
hedging diesel with a crude-oil strike) must be stated explicitly. Do not call `hedge`
until the set is worth sizing.

`present_hedge` is the last step. When none fits, call it with `verdict=none` and no
candidate or `why_this_pays`; do not call `hedge`. When a ticker is kept, call `hedge`
then `present_hedge` with that payload unmodified as `candidate`, plus `headline`,
`why_this_pays`, and `basis_risk`. Paste `markdown` as the user reply; do not restate
dollars in different figures.

openhedge does not place orders. Send the user to `url` on the source venue.
"""

_HEDGE_CARD_TEMPLATE = Environment(
    loader=PackageLoader("openhedge_core", "templates"),
    autoescape=False,
).get_template("hedge_card.j2")


class HedgeParams(BaseModel):
    """Inputs for sizing a cash-flow hedge on one market the agent already chose."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(
        min_length=1,
        description="Market primary key from search_markets, browse_markets, or get_event.",
    )
    side: HedgeSide = Field(
        default="yes",
        description=(
            "Contract side to buy: the side that pays $1 if the adverse outcome occurs. "
            "Default yes. Use no when this market's NO resolution is the hedge."
        ),
    )
    estimated_hit_dollars: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Modeled dollar loss if the adverse event happens. Omit to get unit economics "
            "(contracts sized for $1 of payout) without residual P&L."
        ),
    )
    coverage: float = Field(
        default=1.0,
        gt=0,
        le=1,
        description=(
            "Fraction of estimated_hit_dollars to target as gross Kalshi payout. "
            "Ignored for the target when no hit is given. Defaults to 1.0 (full offset)."
        ),
    )


class HedgeCandidate(BaseModel):
    """One chosen market sized as a binary cash-flow hedge."""

    ticker: str = Field(description="Market primary key.")
    url: str = Field(description="Canonical URL of the market on the source platform.")
    question: str = Field(description="Question of the market.")
    source: MarketSource = Field(description="Source platform of the market.")
    side: HedgeSide = Field(description="Side bought: yes or no.")
    price_per_contract: float = Field(
        description="Best ask for `side` in dollars. For no, this is 1 minus yes_bid_price.",
    )
    available_size: float = Field(description="Contract size quoted at that ask.")
    contracts: float = Field(description="Contracts to buy, snapped to 0.01 and capped by available_size.")
    premium_dollars: float = Field(
        description="Upfront cost: contracts times price_per_contract. Ignores Kalshi trade and rounding fees."
    )
    gross_payout_dollars: float = Field(
        description="Gross settlement if `side` wins: contracts times $1.",
    )
    estimated_hit_dollars: float | None = Field(
        default=None,
        description="Modeled dollar loss passed to hedge. Null for unit economics.",
    )
    coverage: float = Field(
        description=(
            "Requested fraction of estimated_hit_dollars targeted as gross payout. "
            "Ignored for the target when no hit was given."
        ),
    )
    target_payout_dollars: float = Field(
        description=(
            "Unconstrained gross payout target: estimated_hit_dollars times coverage, or $1 when no hit was given."
        ),
    )
    unconstrained_contracts: float = Field(
        description="Contract count implied by target_payout_dollars before the book cap.",
    )
    coverage_achieved: float | None = Field(
        default=None,
        description=(
            "gross_payout_dollars divided by estimated_hit_dollars. Null when no dollar "
            "hit was given. This is payout versus modeled loss, not versus requested coverage."
        ),
    )
    net_if_pays: float | None = Field(
        default=None,
        description=(
            "estimated_hit_dollars minus gross_payout_dollars minus premium_dollars. "
            "Ignores fees. Null when no dollar hit was given."
        ),
    )
    net_if_expires: float | None = Field(
        default=None,
        description="Cash result if `side` loses: minus premium_dollars. Ignores fees. Null when no dollar hit was given.",
    )
    liquidity_constrained: bool = Field(
        description=(
            "True when top-of-book available_size is smaller than the unconstrained contract count. "
            "Size is capped at that ask; deeper book levels are not used."
        ),
    )


class HedgeCardParams(BaseModel):
    """Inputs for formatting a prior hedge result as a user-facing card."""

    model_config = ConfigDict(extra="forbid")

    verdict: HedgeVerdict = Field(description="fit when a sized candidate is kept; none when no market maps cleanly.")
    headline: str = Field(min_length=1, description="Restated user exposure in one line.")
    why_this_pays: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Why this market pays when the exposure hits. Required for fit; omit for none. "
            "Do not put dollar figures here."
        ),
    )
    basis_risk: str = Field(
        min_length=1,
        description="Why this market is a proxy (or why none fits). Do not put dollar figures here.",
    )
    other_exposures: list[str] = Field(
        default_factory=list,
        description="Optional related risks noticed but not sized on this card.",
    )
    candidate: HedgeCandidate | None = Field(
        default=None,
        description="Unmodified hedge tool result. Required for fit; omit for none.",
    )

    @model_validator(mode="after")
    def _verdict_matches_candidate(self) -> Self:
        if self.verdict == "fit" and self.candidate is None:
            raise ValueError("verdict=fit requires candidate")
        if self.verdict == "none" and self.candidate is not None:
            raise ValueError("verdict=none rejects candidate")
        if self.verdict == "fit" and self.why_this_pays is None:
            raise ValueError("verdict=fit requires why_this_pays")
        if self.verdict == "none" and self.why_this_pays is not None:
            raise ValueError("verdict=none rejects why_this_pays")
        return self


class HedgeCard(BaseModel):
    """Blanket-style hedge card: agent narrative plus server-owned dollars."""

    verdict: HedgeVerdict = Field(description="fit or none.")
    headline: str = Field(description="Restated user exposure in one line.")
    why_this_pays: str | None = Field(
        default=None,
        description="Why this market pays when the exposure hits. Null when verdict is none.",
    )
    basis_risk: str = Field(description="Why this market is a proxy, or why none fits.")
    other_exposures: list[str] = Field(description="Related risks noticed but not sized on this card.")
    candidate: HedgeCandidate | None = Field(
        default=None,
        description="Sized hedge copied from the inbound candidate. Null when verdict is none.",
    )
    markdown: str = Field(description="Frozen user reply. Paste this verbatim; do not restate dollars.")


def size_hedge(market: Market, params: HedgeParams) -> HedgeCandidate:
    """Size a buy of `params.side` on `market` from top-of-book ask and optional dollar hit."""
    price, available_size = _ask_for_side(market, params.side)
    estimated_hit_dollars = params.estimated_hit_dollars
    coverage = params.coverage
    target_payout = estimated_hit_dollars * coverage if estimated_hit_dollars is not None else UNIT_PAYOUT_DOLLARS
    unconstrained = round(target_payout, CONTRACT_PRECISION)
    contracts = min(unconstrained, round(available_size, CONTRACT_PRECISION))
    premium = round(contracts * price, CONTRACT_PRECISION)
    gross_payout = round(contracts * UNIT_PAYOUT_DOLLARS, CONTRACT_PRECISION)
    net_if_pays: float | None = None
    net_if_expires: float | None = None
    coverage_achieved: float | None = None
    if estimated_hit_dollars is not None:
        net_if_pays = round(estimated_hit_dollars - gross_payout - premium, CONTRACT_PRECISION)
        net_if_expires = round(-premium, CONTRACT_PRECISION)
        coverage_achieved = round(gross_payout / estimated_hit_dollars, COVERAGE_ACHIEVED_DECIMALS)
    return HedgeCandidate(
        ticker=market.ticker,
        url=market.url,
        question=market.question,
        source=market.source,
        side=params.side,
        price_per_contract=round(price, PRICE_DECIMALS),
        available_size=round(available_size, CONTRACT_PRECISION),
        contracts=contracts,
        premium_dollars=premium,
        gross_payout_dollars=gross_payout,
        estimated_hit_dollars=estimated_hit_dollars,
        coverage=coverage,
        target_payout_dollars=round(target_payout, CONTRACT_PRECISION),
        unconstrained_contracts=unconstrained,
        coverage_achieved=coverage_achieved,
        net_if_pays=net_if_pays,
        net_if_expires=net_if_expires,
        liquidity_constrained=available_size < unconstrained,
    )


def compose_hedge_card(params: HedgeCardParams) -> HedgeCard:
    """Copy inbound candidate numbers into a frozen markdown card. Does not re-size."""
    return HedgeCard(
        verdict=params.verdict,
        headline=params.headline,
        why_this_pays=params.why_this_pays,
        basis_risk=params.basis_risk,
        other_exposures=list(params.other_exposures),
        candidate=params.candidate,
        markdown=render_hedge_card(params),
    )


def render_hedge_card(params: HedgeCardParams) -> str:
    """Render the user-facing hedge card markdown from already-validated params."""
    candidate = params.candidate
    context: dict[str, object] = {
        "verdict": params.verdict,
        "headline": params.headline,
        "why_this_pays": params.why_this_pays,
        "basis_risk": params.basis_risk,
        "other_exposures": params.other_exposures,
        "unit_economics": False,
        "liquidity_constrained": False,
    }
    if candidate is not None:
        context.update(
            {
                "question": candidate.question,
                "source": _format_source(candidate.source),
                "side": candidate.side.upper(),
                "url": candidate.url,
                "premium": _format_dollars(candidate.premium_dollars),
                "gross": _format_dollars(candidate.gross_payout_dollars),
                "hit": _format_dollars(candidate.estimated_hit_dollars)
                if candidate.estimated_hit_dollars is not None
                else None,
                "hit_signed": _format_dollars(-(candidate.estimated_hit_dollars or 0.0)),
                "gross_signed": _format_signed_dollars(candidate.gross_payout_dollars),
                "premium_signed": _format_dollars(-candidate.premium_dollars),
                "net_if_pays": _format_dollars(candidate.net_if_pays) if candidate.net_if_pays is not None else None,
                "net_if_expires": _format_dollars(candidate.net_if_expires)
                if candidate.net_if_expires is not None
                else None,
                "unit_economics": candidate.estimated_hit_dollars is None,
                "liquidity_constrained": candidate.liquidity_constrained,
                "unconstrained_contracts": _format_count(candidate.unconstrained_contracts),
                "available_size": _format_count(candidate.available_size),
                "contracts": _format_count(candidate.contracts),
                "target": _format_dollars(candidate.target_payout_dollars),
                "coverage_achieved": _format_coverage(candidate.coverage_achieved),
            }
        )
    return _HEDGE_CARD_TEMPLATE.render(**context).strip()


def _ask_for_side(market: Market, side: HedgeSide) -> tuple[float, float]:
    if side == "yes":
        return market.yes_ask_price, market.yes_ask_size
    return 1.0 - market.yes_bid_price, market.yes_bid_size


def _format_source(source: MarketSource) -> str:
    return source.value.replace("_", " ").title()


def _format_dollars(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _format_signed_dollars(value: float) -> str:
    sign = "-" if value < 0 else "+"
    return f"{sign}${abs(value):,.2f}"


def _format_count(value: float) -> str:
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _format_coverage(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:.{COVERAGE_ACHIEVED_DECIMALS}f}".rstrip("0").rstrip(".")
