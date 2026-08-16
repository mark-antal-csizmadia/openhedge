from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from openhedge_core.embeddings import OpenRouterEmbeddingClient
from openrouter import OpenRouter
from openrouter.operations import CreateEmbeddingsData, CreateEmbeddingsResponseBody


def _client(response: CreateEmbeddingsResponseBody | None = None) -> tuple[OpenRouter, AsyncMock]:
    generate_async = AsyncMock(return_value=response)
    client = MagicMock()
    client.embeddings.generate_async = generate_async
    return cast(OpenRouter, client), generate_async


def _response(*items: tuple[list[float] | str, int | None]) -> CreateEmbeddingsResponseBody:
    return CreateEmbeddingsResponseBody(
        data=[CreateEmbeddingsData(embedding=embedding, object="embedding", index=index) for embedding, index in items],
        model="openai/text-embedding-3-small",
        object="list",
    )


@pytest.mark.asyncio
async def test_embed_batch_skips_empty_input() -> None:
    client, generate_async = _client()
    embedder = OpenRouterEmbeddingClient(client, model="openai/text-embedding-3-small", dimensions=8)

    assert await embedder.embed_batch([]) == []
    generate_async.assert_not_called()


@pytest.mark.asyncio
async def test_embed_batch_forwards_model_and_dimensions() -> None:
    client, generate_async = _client(_response(([0.1, 0.2], 0), ([0.3, 0.4], 1)))
    embedder = OpenRouterEmbeddingClient(client, model="custom/model", dimensions=2)

    vectors = await embedder.embed_batch(["alpha", "beta"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    generate_async.assert_awaited_once()
    assert generate_async.await_args is not None
    kwargs = generate_async.await_args.kwargs
    assert kwargs["input"] == ["alpha", "beta"]
    assert kwargs["model"] == "custom/model"
    assert kwargs["dimensions"] == 2
    assert kwargs["encoding_format"] == "float"


@pytest.mark.asyncio
async def test_embed_batch_sorts_by_index() -> None:
    client, _ = _client(_response(([2.0], 1), ([1.0], 0)))
    embedder = OpenRouterEmbeddingClient(client, model="openai/text-embedding-3-small", dimensions=1)

    assert await embedder.embed_batch(["a", "b"]) == [[1.0], [2.0]]
