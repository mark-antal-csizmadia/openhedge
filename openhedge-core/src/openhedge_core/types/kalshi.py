from datetime import timezone
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, NonNegativeFloat, field_validator


class KalshiMarketStatus(StrEnum):
    """Status of a Kalshi market."""

    INITIALIZED = "initialized"
    INACTIVE = "inactive"
    ACTIVE = "active"
    CLOSED = "closed"
    DETERMINED = "determined"
    DISPUTED = "disputed"
    AMENDED = "amended"
    FINALIZED = "finalized"


class KalshiEventStatus(StrEnum):
    """Status of a Kalshi event."""

    UNOPENED = "unopened"
    OPEN = "open"
    CLOSED = "closed"
    SETTLED = "settled"


class KalshiMarket(BaseModel):
    """Kalshi market."""

    ticker: str
    rules_primary: str
    rules_secondary: str
    open_time: AwareDatetime
    close_time: AwareDatetime
    yes_sub_title: str
    no_sub_title: str
    status: KalshiMarketStatus
    last_price_dollars: NonNegativeFloat
    yes_ask_dollars: NonNegativeFloat
    yes_ask_size_fp: NonNegativeFloat
    yes_bid_dollars: NonNegativeFloat
    yes_bid_size_fp: NonNegativeFloat
    volume_fp: NonNegativeFloat
    volume_24h_fp: NonNegativeFloat
    open_interest_fp: NonNegativeFloat

    @field_validator("open_time", "close_time")
    @classmethod
    def to_utc(cls, v: AwareDatetime) -> AwareDatetime:
        return v.astimezone(timezone.utc)


class KalshiEvent(BaseModel):
    """Kalshi event."""

    event_ticker: str
    title: str
    series_ticker: str
    markets: list["KalshiMarket"]


class KalshiSeries(BaseModel):
    """Kalshi series."""

    ticker: str
    category: str | None = None
    tags: list[str] | None = None


class GetKalshiEventsResponse(BaseModel):
    """Response envelope for the Kalshi REST API get events endpoint."""

    events: list[KalshiEvent]
    cursor: str | None = None


class GetKalshiSeriesResponse(BaseModel):
    """Response envelope for the Kalshi REST API get series endpoint."""

    series: KalshiSeries
