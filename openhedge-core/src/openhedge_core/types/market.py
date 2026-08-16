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


class Market(BaseModel):
    """Market."""

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
    tags: list[str] | None = Field(default=None, description="Tags describing the market")
    question: str = Field(..., description="Question of the market")
    description: str = Field(..., description="Description of the market rules and resolutions")
    start_datetime: AwareDatetime = Field(..., description="Start datetime of the market")
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

    @field_validator("start_datetime", "end_datetime", "updated_datetime")
    @classmethod
    def to_utc(cls, v: AwareDatetime | None) -> AwareDatetime | None:
        if v is None:
            return None
        return v.astimezone(timezone.utc)

    @field_serializer("start_datetime", "end_datetime", "updated_datetime")
    def serialize_datetime(self, dt: datetime | None, _info) -> str | None:
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).isoformat()

    @field_serializer(
        "yes_ask_price", "yes_bid_price", "yes_ask_size", "yes_bid_size", "volume", "volume_24hr", "open_interest"
    )
    def serialize_non_negative_float(self, v: NonNegativeFloat, _info) -> float:
        return round(v, 2)

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
        )


class Event(BaseModel):
    """Event."""

    source: MarketSource = Field(..., description="Source platform of the event")
    event_ticker: str = Field(..., description="Event primary key")
    event_title: str = Field(..., description="Event title")
    series_ticker: str | None = Field(default=None, description="Series primary key")
    category: str | None = Field(default=None, description="Category of the event")
    tags: list[str] | None = Field(default=None, description="Tags describing the event")
    markets: list[Market] = Field(..., description="Markets in the event, ordered by strike_order")

    @classmethod
    def from_markets(cls, markets: list[Market]) -> "Event":
        ordered = sorted(markets, key=lambda market: market.strike_order)
        first = ordered[0]
        return cls(
            source=first.source,
            event_ticker=first.event_ticker,
            event_title=first.event_title,
            series_ticker=first.series_ticker,
            category=first.category,
            tags=first.tags,
            markets=ordered,
        )
