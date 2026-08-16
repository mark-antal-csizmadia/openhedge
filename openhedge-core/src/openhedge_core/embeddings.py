from typing import Protocol

from jinja2 import Environment, PackageLoader
from openrouter import OpenRouter
from openrouter.operations import CreateEmbeddingsResponseBody

from openhedge_core.types.market import Market

DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIM = 768

_EMBEDDING_TEXT_TEMPLATE = Environment(
    loader=PackageLoader("openhedge_core", "templates"),
    autoescape=False,
).get_template("embedding_text.j2")


def market_embedding_text(market: Market) -> str:
    return _EMBEDDING_TEXT_TEMPLATE.render(
        event_title=market.event_title,
        yes_outcome=market.yes_outcome,
        no_outcome=market.no_outcome,
    ).strip()


class EmbeddingClient(Protocol):
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OpenRouterEmbeddingClient:
    def __init__(self, client: OpenRouter, *, model: str, dimensions: int) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.embeddings.generate_async(
            input=texts,
            model=self._model,
            dimensions=self._dimensions,
            encoding_format="float",
        )
        if not isinstance(response, CreateEmbeddingsResponseBody):
            raise TypeError(f"expected embeddings JSON response, got {type(response).__name__}")
        items = sorted(
            enumerate(response.data),
            key=lambda pair: pair[1].index if pair[1].index is not None else pair[0],
        )
        vectors: list[list[float]] = []
        for _, item in items:
            embedding = item.embedding
            if not isinstance(embedding, list):
                raise TypeError("expected float embeddings, got encoded string")
            vectors.append(embedding)
        if len(vectors) != len(texts):
            raise ValueError(f"expected {len(texts)} embeddings, got {len(vectors)}")
        return vectors
