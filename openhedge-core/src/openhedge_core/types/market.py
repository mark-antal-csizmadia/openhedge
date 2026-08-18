from collections.abc import Sequence
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    field_serializer,
    field_validator,
)

from openhedge_core.types.kalshi import KalshiEvent, KalshiMarket, KalshiSeries


class MarketSource(str, Enum):
    """Source platform of the market."""

    KALSHI = "kalshi"


PRICE_DECIMALS = 4
COUNT_DECIMALS = 2


def _serialize_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _serialize_price(v: NonNegativeFloat) -> float:
    return round(v, PRICE_DECIMALS)


def _serialize_count(v: NonNegativeFloat) -> float:
    return round(v, COUNT_DECIMALS)


class MarketSummary(BaseModel):
    """Compact market fields for list and event responses."""

    source: MarketSource = Field(
        ...,
        description="Source platform of the market data",
    )
    ticker: str = Field(..., description="Market primary key")
    event_ticker: str = Field(
        ...,
        description="Event primary key",
    )
    series_ticker: str = Field(..., description="Series primary key")
    event_title: str = Field(..., description="Event title")
    strike_order: NonNegativeInt = Field(..., description="Index of the market within the source event markets list")
    url: str = Field(..., description="Canonical URL of the market on the source platform")
    category: str | None = Field(default=None, description="Category of the market")
    question: str = Field(..., description="Question of the market")
    end_datetime: AwareDatetime = Field(..., description="End datetime of the market")
    yes_outcome: str = Field(..., description="YES outcome of the market")
    no_outcome: str = Field(..., description="NO outcome of the market")
    yes_ask_price: NonNegativeFloat = Field(
        ...,
        description="Price for the lowest YES sell offer on this market in dollars. This, plus the price for the highest NO buy offer on this market in dollars equals 1.0.",
    )
    yes_ask_size: NonNegativeFloat = Field(
        ...,
        description="Total contract size of orders to sell YES at the best ask price",
    )
    yes_bid_price: NonNegativeFloat = Field(
        ...,
        description="Price for the highest YES buy offer on this market in dollars. This, plus the price for the lowest NO sell offer on this market in dollars equals 1.0.",
    )
    yes_bid_size: NonNegativeFloat = Field(
        ...,
        description="Total contract size of orders to buy YES at the best bid price",
    )

    @field_validator("end_datetime")
    @classmethod
    def end_datetime_to_utc(cls, v: AwareDatetime) -> AwareDatetime:
        return v.astimezone(timezone.utc)

    @field_serializer("end_datetime")
    def serialize_end_datetime(self, dt: datetime, _info) -> str:
        return _serialize_datetime(dt)

    @field_serializer("yes_ask_price")
    def serialize_yes_ask_price(self, v: NonNegativeFloat, _info) -> float:
        return _serialize_price(v)

    @field_serializer("yes_ask_size")
    def serialize_yes_ask_size(self, v: NonNegativeFloat, _info) -> float:
        return _serialize_count(v)

    @field_serializer("yes_bid_price")
    def serialize_yes_bid_price(self, v: NonNegativeFloat, _info) -> float:
        return _serialize_price(v)

    @field_serializer("yes_bid_size")
    def serialize_yes_bid_size(self, v: NonNegativeFloat, _info) -> float:
        return _serialize_count(v)


MARKET_SUMMARY_PAYLOAD_FIELDS: tuple[str, ...] = tuple(MarketSummary.model_fields)


class Market(MarketSummary):
    """Full market record, including resolution rules and volume."""

    tags: list[str] | None = Field(default=None, description="Tags describing the market")
    description: str = Field(..., description="Description of the market rules and resolutions")
    start_datetime: AwareDatetime = Field(..., description="Start datetime of the market")
    volume: NonNegativeFloat = Field(
        ...,
        description="Volume of the market",
    )
    volume_24hr: NonNegativeFloat = Field(
        ...,
        description="Volume of the market in the last 24 hours",
    )
    open_interest: NonNegativeFloat = Field(
        ...,
        description="Open interest of the market",
    )
    updated_datetime: AwareDatetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Timestamp of the last update",
    )
    can_close_early: bool = Field(
        default=False,
        description=(
            "Whether this market can close before end_datetime. When true, trading may stop "
            "earlier if early_close_condition is met."
        ),
    )
    early_close_condition: str | None = Field(
        default=None,
        description=(
            "Plain-language condition under which the market can close early. Null when "
            "can_close_early is false or the source omitted it."
        ),
    )

    @field_validator("start_datetime")
    @classmethod
    def start_datetime_to_utc(cls, v: AwareDatetime) -> AwareDatetime:
        return v.astimezone(timezone.utc)

    @field_validator("updated_datetime")
    @classmethod
    def updated_datetime_to_utc(cls, v: AwareDatetime | None) -> AwareDatetime | None:
        if v is None:
            return None
        return v.astimezone(timezone.utc)

    @field_serializer("start_datetime")
    def serialize_start_datetime(self, dt: datetime, _info) -> str:
        return _serialize_datetime(dt)

    @field_serializer("updated_datetime")
    def serialize_updated_datetime(self, dt: datetime | None, _info) -> str | None:
        if dt is None:
            return None
        return _serialize_datetime(dt)

    @field_serializer("volume")
    def serialize_volume(self, v: NonNegativeFloat, _info) -> float:
        return _serialize_count(v)

    @field_serializer("volume_24hr")
    def serialize_volume_24hr(self, v: NonNegativeFloat, _info) -> float:
        return _serialize_count(v)

    @field_serializer("open_interest")
    def serialize_open_interest(self, v: NonNegativeFloat, _info) -> float:
        return _serialize_count(v)

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @staticmethod
    def kalshi_url(*, ticker: str, event_ticker: str, series_ticker: str) -> str:
        return f"https://kalshi.com/markets/{series_ticker}/{event_ticker}?op_market_ticker={ticker}"

    @classmethod
    def from_kalshi_rest_api(
        cls,
        kalshi_event: KalshiEvent,
        kalshi_market: KalshiMarket,
        kalshi_series: KalshiSeries,
        *,
        strike_order: NonNegativeInt,
    ) -> "Market":
        return cls(
            source=MarketSource.KALSHI,
            ticker=kalshi_market.ticker,
            event_ticker=kalshi_event.event_ticker,
            event_title=kalshi_event.title,
            series_ticker=kalshi_series.ticker,
            strike_order=strike_order,
            url=cls.kalshi_url(
                ticker=kalshi_market.ticker, event_ticker=kalshi_event.event_ticker, series_ticker=kalshi_series.ticker
            ),
            category=kalshi_series.category,
            tags=kalshi_series.tags,
            question=kalshi_market.yes_sub_title + " - " + kalshi_event.title,
            description=kalshi_market.rules_primary + " " + kalshi_market.rules_secondary,
            start_datetime=kalshi_market.open_time,
            end_datetime=kalshi_market.close_time,
            yes_outcome=kalshi_market.yes_sub_title,
            no_outcome=kalshi_market.no_sub_title,
            yes_ask_price=kalshi_market.yes_ask_dollars,
            yes_ask_size=kalshi_market.yes_ask_size_fp,
            yes_bid_price=kalshi_market.yes_bid_dollars,
            yes_bid_size=kalshi_market.yes_bid_size_fp,
            volume=kalshi_market.volume_fp,
            volume_24hr=kalshi_market.volume_24h_fp,
            open_interest=kalshi_market.open_interest_fp,
            can_close_early=kalshi_market.can_close_early,
            early_close_condition=kalshi_market.early_close_condition,
        )


class Event(BaseModel):
    """Event."""

    source: MarketSource = Field(..., description="Source platform of the event")
    event_ticker: str = Field(..., description="Event primary key")
    event_title: str = Field(..., description="Event title")
    series_ticker: str | None = Field(default=None, description="Series primary key")
    category: str | None = Field(default=None, description="Category of the event")
    markets: list[MarketSummary] = Field(..., description="Markets in the event, ordered by strike_order")
    market_count: int = Field(..., description="Number of markets in the event")

    @classmethod
    def from_markets(cls, markets: Sequence[MarketSummary]) -> "Event":
        ordered = sorted(
            (MarketSummary.model_validate(market.model_dump()) for market in markets),
            key=lambda market: market.strike_order,
        )
        first = ordered[0]
        return cls(
            source=first.source,
            event_ticker=first.event_ticker,
            event_title=first.event_title,
            series_ticker=first.series_ticker,
            category=first.category,
            markets=ordered,
            market_count=len(ordered),
        )
