import json
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel

from openhedge_core.server import (
    MarketListParams,
    MarketPage,
    MarketSearchParams,
    ReadyStatus,
    VocabList,
    VocabListParams,
)
from openhedge_core.types.market import Event, Market

T = TypeVar("T", bound=BaseModel)


class MarketApi(Protocol):
    async def ready(self) -> ReadyStatus: ...
    async def browse_markets(self, params: MarketListParams) -> MarketPage: ...
    async def search_markets(self, params: MarketSearchParams) -> MarketPage: ...
    async def get_market(self, ticker: str) -> Market: ...
    async def get_event(self, event_ticker: str) -> Event: ...
    async def list_categories(self, params: VocabListParams) -> VocabList: ...
    async def list_tags(self, params: VocabListParams) -> VocabList: ...


class OpenhedgeApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


class OpenhedgeApiClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @classmethod
    def from_base_url(cls, base_url: str, *, timeout: float = 30.0) -> "OpenhedgeApiClient":
        return cls(httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ready(self) -> ReadyStatus:
        return await self._get("/ready", ReadyStatus)

    async def browse_markets(self, params: MarketListParams) -> MarketPage:
        return await self._get("/v1/markets", MarketPage, params=params)

    async def search_markets(self, params: MarketSearchParams) -> MarketPage:
        return await self._post("/v1/search", MarketPage, params=params)

    async def get_market(self, ticker: str) -> Market:
        return await self._get(f"/v1/markets/{ticker}", Market)

    async def get_event(self, event_ticker: str) -> Event:
        return await self._get(f"/v1/events/{event_ticker}", Event)

    async def list_categories(self, params: VocabListParams) -> VocabList:
        return await self._get("/v1/categories", VocabList, params=params)

    async def list_tags(self, params: VocabListParams) -> VocabList:
        return await self._get("/v1/tags", VocabList, params=params)

    async def _get(self, path: str, model: type[T], *, params: BaseModel | None = None) -> T:
        query = params.model_dump(mode="json", exclude_none=True) if params is not None else None
        return self._parse(await self._client.get(path, params=query), model)

    async def _post(self, path: str, model: type[T], *, params: BaseModel) -> T:
        return self._parse(
            await self._client.post(path, json=params.model_dump(mode="json", exclude_none=True)),
            model,
        )

    def _parse(self, response: httpx.Response, model: type[T]) -> T:
        if response.status_code >= 400:
            raise OpenhedgeApiError(response.status_code, _response_detail(response))
        return model.model_validate(response.json())


def _response_detail(response: httpx.Response) -> str:
    try:
        payload: Any = response.json()
    except ValueError:
        text = response.text.strip()
        return text or response.reason_phrase
    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
        if isinstance(detail, str):
            return detail
        return json.dumps(detail)
    text = response.text.strip()
    return text or response.reason_phrase
