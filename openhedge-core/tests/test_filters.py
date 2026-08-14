from datetime import datetime, timezone

from openhedge_core.filters import FILTERABLE_FIELDS, MarketFilters, to_qdrant_filter
from openhedge_core.types.market import MarketSource
from openhedge_core.vector_store import QdrantVectorStore
from qdrant_client.models import DatetimeRange, FieldCondition, MatchAny, MatchValue, Range


def _filter_field_name(name: str) -> str:
    for suffix in ("_gte", "_lte"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def test_market_filters_cover_payload_indexes() -> None:
    names = {_filter_field_name(name) for name in MarketFilters.model_fields}
    assert names == FILTERABLE_FIELDS == set(QdrantVectorStore.PAYLOAD_INDEXES)


def test_empty_filters_are_none() -> None:
    assert to_qdrant_filter(MarketFilters()) is None


def test_empty_keyword_list_is_ignored() -> None:
    assert to_qdrant_filter(MarketFilters(category=[])) is None


def test_single_keyword_uses_match_value() -> None:
    qfilter = to_qdrant_filter(MarketFilters(source=[MarketSource.KALSHI], category=["Politics"]))
    assert qfilter is not None
    conditions = [condition for condition in qfilter.must or [] if isinstance(condition, FieldCondition)]
    by_key = {condition.key: condition.match for condition in conditions}
    assert by_key["source"] == MatchValue(value="kalshi")
    assert by_key["category"] == MatchValue(value="Politics")


def test_multiple_keywords_use_match_any() -> None:
    qfilter = to_qdrant_filter(MarketFilters(ticker=["A", "B"], tags=["fed", "rates"]))
    assert qfilter is not None
    conditions = [condition for condition in qfilter.must or [] if isinstance(condition, FieldCondition)]
    by_key = {condition.key: condition.match for condition in conditions}
    assert by_key["ticker"] == MatchAny(any=["A", "B"])
    assert by_key["tags"] == MatchAny(any=["fed", "rates"])


def test_float_range() -> None:
    qfilter = to_qdrant_filter(MarketFilters(price_yes_gte=0.1, price_yes_lte=0.5, volume_gte=1000))
    assert qfilter is not None
    conditions = [condition for condition in qfilter.must or [] if isinstance(condition, FieldCondition)]
    by_key = {condition.key: condition.range for condition in conditions}
    assert by_key["price_yes"] == Range(gte=0.1, lte=0.5)
    assert by_key["volume"] == Range(gte=1000, lte=None)


def test_datetime_range() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 12, 31, tzinfo=timezone.utc)
    qfilter = to_qdrant_filter(MarketFilters(end_datetime_gte=start, end_datetime_lte=end))
    assert qfilter is not None
    conditions = [condition for condition in qfilter.must or [] if isinstance(condition, FieldCondition)]
    assert len(conditions) == 1
    assert conditions[0].key == "end_datetime"
    assert conditions[0].range == DatetimeRange(gte=start, lte=end)
