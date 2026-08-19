from unittest.mock import AsyncMock, patch

import pytest
from openhedge_core.settings import SetupQdrantSettings
from openhedge_core.setup_qdrant import setup_collection
from tenacity import RetryError


@pytest.mark.asyncio
async def test_setup_collection_succeeds() -> None:
    settings = SetupQdrantSettings()
    mock_client = AsyncMock()
    mock_store = AsyncMock()
    with (
        patch("openhedge_core.setup_qdrant.AsyncQdrantClient", return_value=mock_client) as mock_client_cls,
        patch("openhedge_core.setup_qdrant.QdrantVectorStore", return_value=mock_store) as mock_store_cls,
    ):
        await setup_collection(settings)

    mock_client_cls.assert_called_once_with(url=settings.qdrant.url, api_key=settings.qdrant.api_key)
    mock_store_cls.assert_called_once_with(
        mock_client,
        collection=settings.qdrant.collection,
        point_id_namespace=settings.qdrant.point_id_namespace,
    )
    mock_store.setup.assert_awaited_once_with(vector_size=settings.openrouter.embedding_dim)
    mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_collection_retries_then_succeeds() -> None:
    settings = SetupQdrantSettings()
    mock_client = AsyncMock()
    mock_store = AsyncMock()
    mock_store.setup.side_effect = [ConnectionError("qdrant down"), None]
    with (
        patch("openhedge_core.setup_qdrant.AsyncQdrantClient", return_value=mock_client),
        patch("openhedge_core.setup_qdrant.QdrantVectorStore", return_value=mock_store),
        patch("tenacity.nap.sleep", return_value=None),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await setup_collection(settings)

    assert mock_store.setup.await_count == 2
    assert mock_client.close.await_count == 2


@pytest.mark.asyncio
async def test_setup_collection_reraises_after_retries() -> None:
    settings = SetupQdrantSettings()
    mock_client = AsyncMock()
    mock_store = AsyncMock()
    mock_store.setup.side_effect = ConnectionError("qdrant down")
    with (
        patch("openhedge_core.setup_qdrant.AsyncQdrantClient", return_value=mock_client),
        patch("openhedge_core.setup_qdrant.QdrantVectorStore", return_value=mock_store),
        patch("tenacity.nap.sleep", return_value=None),
        patch("asyncio.sleep", new_callable=AsyncMock),
        pytest.raises((ConnectionError, RetryError)),
    ):
        await setup_collection(settings)

    assert mock_store.setup.await_count == 8
    assert mock_client.close.await_count == 8
