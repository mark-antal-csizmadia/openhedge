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
    KALSHI = "kalshi"


class Market(BaseModel):
    source: MarketSource = Field(
        ...,
        description="Source platform of the market data",
    )
    ticker: str = Field(..., description="Market primary key")
    event_ticker: str = Field(
        ...,
        description="Event primary key",
    )
    event_title: str = Field(..., description="Event title")
    series_ticker: str | None = Field(default=None, description="Series primary key")
    strike_order: NonNegativeInt = Field(..., description="Index of the market within the source event markets list")
    url: str = Field(..., description="Canonical URL of the market on the source platform")
    category: str | None = Field(default=None, description="Category of the market")
    tags: list[str] | None = Field(default=None, description="Tags describing the market")
    question: str = Field(..., description="Question of the market")
    description: str = Field(..., description="Description of the market rules and resolutions")
    start_datetime: AwareDatetime | None = Field(default=None, description="Start datetime of the market")
    end_datetime: AwareDatetime | None = Field(default=None, description="End datetime of the market")
    outcome_yes: str = Field(..., description="Yes outcome of the market")
    outcome_no: str = Field(..., description="No outcome of the market")
    price_yes: NonNegativeFloat = Field(
        ...,
        description="Price of the yes outcome",
    )
    price_no: NonNegativeFloat = Field(
        ...,
        description="Price of the no outcome",
    )
    volume: NonNegativeFloat | None = Field(
        default=None,
        description="Volume of the market",
    )
    volume_24hr: NonNegativeFloat | None = Field(
        default=None,
        description="Volume of the market in the last 24 hours",
    )
    open_interest: NonNegativeFloat | None = Field(
        default=None,
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

    @field_serializer("price_yes", "price_no")
    def serialize_non_negative_float(self, v: NonNegativeFloat, _info) -> float:
        return round(v, 2)

    @field_serializer("volume", "volume_24hr", "open_interest")
    def serialize_non_negative_float_or_none(self, v: NonNegativeFloat | None, _info) -> float | None:
        if v is None:
            return None
        else:
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
        question = kalshi_market.yes_sub_title.lower() + " - " + kalshi_event.title.lower()
        ticker = kalshi_market.ticker
        event_ticker = kalshi_event.event_ticker
        series_ticker = kalshi_series.ticker
        return cls(
            source=MarketSource.KALSHI,
            ticker=ticker,
            event_ticker=event_ticker,
            event_title=kalshi_event.title,
            series_ticker=series_ticker,
            strike_order=strike_order,
            url=cls.kalshi_url(ticker=ticker, event_ticker=event_ticker, series_ticker=series_ticker),
            category=kalshi_series.category,
            tags=kalshi_series.tags,
            question=question,
            description=kalshi_market.rules_primary + " " + kalshi_market.rules_secondary,
            start_datetime=kalshi_market.open_time,
            end_datetime=kalshi_market.close_time,
            outcome_yes=kalshi_market.yes_sub_title,
            outcome_no=kalshi_market.no_sub_title,
            price_yes=kalshi_market.last_price_dollars,
            price_no=1.0 - kalshi_market.last_price_dollars,
            volume=kalshi_market.volume_fp,
            volume_24hr=kalshi_market.volume_24h_fp,
            open_interest=kalshi_market.open_interest_fp,
        )


class Event(BaseModel):
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
