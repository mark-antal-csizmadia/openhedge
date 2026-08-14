from enum import Enum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from qdrant_client.models import Condition, DatetimeRange, FieldCondition, Filter, MatchAny, MatchValue, Range

from openhedge_core.types.market import MarketSource

KEYWORD_FILTER_FIELDS: tuple[str, ...] = (
    "source",
    "ticker",
    "event_ticker",
    "series_ticker",
    "category",
    "tags",
)
DATETIME_FILTER_FIELDS: tuple[str, ...] = ("start_datetime", "end_datetime")
FLOAT_FILTER_FIELDS: tuple[str, ...] = (
    "price_yes",
    "price_no",
    "volume",
    "volume_24hr",
    "open_interest",
)
FILTERABLE_FIELDS: frozenset[str] = frozenset(KEYWORD_FILTER_FIELDS + DATETIME_FILTER_FIELDS + FLOAT_FILTER_FIELDS)


class MarketFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: list[MarketSource] | None = Field(
        default=None,
        description="Source platforms to include. Multiple values are OR'd. Currently `kalshi`.",
    )
    ticker: list[str] | None = Field(
        default=None,
        description="Market tickers to include. Multiple values are OR'd.",
    )
    event_ticker: list[str] | None = Field(
        default=None,
        description="Event tickers to include. Multiple values are OR'd.",
    )
    series_ticker: list[str] | None = Field(
        default=None,
        description="Series tickers to include. Multiple values are OR'd.",
    )
    category: list[str] | None = Field(
        default=None,
        description="Market categories to include (for example Politics). Multiple values are OR'd.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Tags to include. Multiple values are OR'd.",
    )
    start_datetime_gte: AwareDatetime | None = Field(
        default=None,
        description="Inclusive lower bound on market start datetime (timezone-aware ISO-8601).",
    )
    start_datetime_lte: AwareDatetime | None = Field(
        default=None,
        description="Inclusive upper bound on market start datetime (timezone-aware ISO-8601).",
    )
    end_datetime_gte: AwareDatetime | None = Field(
        default=None,
        description="Inclusive lower bound on market end datetime (timezone-aware ISO-8601).",
    )
    end_datetime_lte: AwareDatetime | None = Field(
        default=None,
        description="Inclusive upper bound on market end datetime (timezone-aware ISO-8601).",
    )
    price_yes_gte: float | None = Field(
        default=None,
        description="Inclusive lower bound on yes-outcome price. Prices are probabilities in [0, 1].",
    )
    price_yes_lte: float | None = Field(
        default=None,
        description="Inclusive upper bound on yes-outcome price. Prices are probabilities in [0, 1].",
    )
    price_no_gte: float | None = Field(
        default=None,
        description="Inclusive lower bound on no-outcome price. Prices are probabilities in [0, 1].",
    )
    price_no_lte: float | None = Field(
        default=None,
        description="Inclusive upper bound on no-outcome price. Prices are probabilities in [0, 1].",
    )
    volume_gte: float | None = Field(
        default=None,
        description="Inclusive lower bound on lifetime traded volume.",
    )
    volume_lte: float | None = Field(
        default=None,
        description="Inclusive upper bound on lifetime traded volume.",
    )
    volume_24hr_gte: float | None = Field(
        default=None,
        description="Inclusive lower bound on volume traded in the last 24 hours.",
    )
    volume_24hr_lte: float | None = Field(
        default=None,
        description="Inclusive upper bound on volume traded in the last 24 hours.",
    )
    open_interest_gte: float | None = Field(
        default=None,
        description="Inclusive lower bound on open interest.",
    )
    open_interest_lte: float | None = Field(
        default=None,
        description="Inclusive upper bound on open interest.",
    )


def to_qdrant_filter(filters: MarketFilters) -> Filter | None:
    data = filters.model_dump(exclude_none=True, exclude={"limit", "cursor", "q"})
    must: list[Condition] = []
    must.extend(_keyword_conditions(data))
    must.extend(_datetime_conditions(data))
    must.extend(_float_conditions(data))
    if not must:
        return None
    return Filter(must=must)


def _keyword_conditions(data: dict[str, Any]) -> list[FieldCondition]:
    conditions: list[FieldCondition] = []
    for field in KEYWORD_FILTER_FIELDS:
        values = data.get(field)
        if not values:
            continue
        normalized = [_keyword_value(value) for value in values]
        if len(normalized) == 1:
            conditions.append(FieldCondition(key=field, match=MatchValue(value=normalized[0])))
        else:
            conditions.append(FieldCondition(key=field, match=MatchAny(any=normalized)))
    return conditions


def _datetime_conditions(data: dict[str, Any]) -> list[FieldCondition]:
    conditions: list[FieldCondition] = []
    for field in DATETIME_FILTER_FIELDS:
        gte = data.get(f"{field}_gte")
        lte = data.get(f"{field}_lte")
        if gte is None and lte is None:
            continue
        conditions.append(FieldCondition(key=field, range=DatetimeRange(gte=gte, lte=lte)))
    return conditions


def _float_conditions(data: dict[str, Any]) -> list[FieldCondition]:
    conditions: list[FieldCondition] = []
    for field in FLOAT_FILTER_FIELDS:
        gte = data.get(f"{field}_gte")
        lte = data.get(f"{field}_lte")
        if gte is None and lte is None:
            continue
        conditions.append(FieldCondition(key=field, range=Range(gte=gte, lte=lte)))
    return conditions


def _keyword_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
