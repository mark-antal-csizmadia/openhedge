from datetime import timezone
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, Field, NonNegativeFloat, field_validator


class KalshiMarketStatus(StrEnum):
    INITIALIZED = "initialized"
    INACTIVE = "inactive"
    ACTIVE = "active"
    CLOSED = "closed"
    DETERMINED = "determined"
    DISPUTED = "disputed"
    AMENDED = "amended"
    FINALIZED = "finalized"


class KalshiEventStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    SETTLED = "settled"


class KalshiMarket(BaseModel):
    ticker: str
    rules_primary: str
    rules_secondary: str
    open_time: AwareDatetime
    close_time: AwareDatetime
    yes_sub_title: str
    no_sub_title: str
    status: KalshiMarketStatus
    last_price_dollars: NonNegativeFloat
    volume_fp: NonNegativeFloat
    volume_24h_fp: NonNegativeFloat | None = Field(
        default=None
    )  # markets shorter than 24 hours may not have a volume24h_fp
    open_interest_fp: NonNegativeFloat

    @field_validator("open_time", "close_time")
    @classmethod
    def to_utc(cls, v: AwareDatetime) -> AwareDatetime:
        return v.astimezone(timezone.utc)


class KalshiEvent(BaseModel):
    event_ticker: str
    title: str
    series_ticker: str
    markets: list["KalshiMarket"]


class KalshiSeries(BaseModel):
    ticker: str
    category: str | None = None
    tags: list[str] | None = None


class GetEventsResponse(BaseModel):
    """Response envelope for the Kalshi REST API get events endpoint."""

    events: list[KalshiEvent]
    cursor: str | None = None


class GetSeriesResponse(BaseModel):
    """Response envelope for the Kalshi REST API get series endpoint."""

    series: KalshiSeries
