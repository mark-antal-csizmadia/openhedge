import pytest
from openhedge_core.embeddings import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIM
from openhedge_core.settings import (
    DEFAULT_OPENROUTER_APP_TITLE,
    DEFAULT_OPENROUTER_HTTP_REFERER,
    McpServerSettings,
    ServerSettings,
    SetupQdrantSettings,
    SyncMarketsSettings,
)
from openhedge_core.vector_store import DEFAULT_POINT_ID_NAMESPACE, DEFAULT_QDRANT_COLLECTION, DEFAULT_QDRANT_URL
from pydantic import ValidationError

_SETTINGS_ENV = (
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "QDRANT_POINT_ID_NAMESPACE",
    "OPENROUTER_API_KEY",
    "OPENROUTER_EMBEDDING_MODEL",
    "OPENROUTER_EMBEDDING_DIM",
    "OPENROUTER_HTTP_REFERER",
    "OPENROUTER_APP_TITLE",
    "API_HOST",
    "API_PORT",
    "MCP_HOST",
    "MCP_PORT",
    "OPENHEDGE_API_URL",
    "BATCH_SIZE",
)


@pytest.fixture(autouse=True)
def clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _SETTINGS_ENV:
        monkeypatch.delenv(key, raising=False)


def test_server_settings_defaults() -> None:
    settings = ServerSettings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.qdrant.url == DEFAULT_QDRANT_URL
    assert settings.qdrant.api_key is None
    assert settings.qdrant.collection == DEFAULT_QDRANT_COLLECTION
    assert settings.qdrant.point_id_namespace == DEFAULT_POINT_ID_NAMESPACE
    assert settings.openrouter.api_key is None
    assert settings.openrouter.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert settings.openrouter.embedding_dim == EMBEDDING_DIM
    assert settings.openrouter.http_referer == DEFAULT_OPENROUTER_HTTP_REFERER
    assert settings.openrouter.app_title == DEFAULT_OPENROUTER_APP_TITLE


def test_mcp_server_settings_defaults() -> None:
    settings = McpServerSettings()
    assert settings.api_url == "http://127.0.0.1:8000"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8001


def test_setup_qdrant_settings_defaults() -> None:
    settings = SetupQdrantSettings()
    assert settings.qdrant.url == DEFAULT_QDRANT_URL
    assert settings.qdrant.collection == DEFAULT_QDRANT_COLLECTION
    assert settings.qdrant.point_id_namespace == DEFAULT_POINT_ID_NAMESPACE
    assert settings.openrouter.embedding_dim == EMBEDDING_DIM


def test_nested_qdrant_and_openrouter_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("QDRANT_COLLECTION", "other")
    monkeypatch.setenv("QDRANT_POINT_ID_NAMESPACE", "https://example.test/markets")
    monkeypatch.setenv("OPENROUTER_EMBEDDING_MODEL", "custom/model")
    monkeypatch.setenv("OPENROUTER_EMBEDDING_DIM", "1024")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://example.test")
    settings = ServerSettings()
    assert settings.qdrant.url == "http://qdrant:6333"
    assert settings.qdrant.collection == "other"
    assert settings.qdrant.point_id_namespace == "https://example.test/markets"
    assert settings.openrouter.embedding_model == "custom/model"
    assert settings.openrouter.embedding_dim == 1024
    assert settings.openrouter.http_referer == "https://example.test"


def test_nested_qdrant_url_keeps_collection_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    settings = ServerSettings()
    assert settings.qdrant.url == "http://qdrant:6333"
    assert settings.qdrant.collection == DEFAULT_QDRANT_COLLECTION
    assert settings.qdrant.point_id_namespace == DEFAULT_POINT_ID_NAMESPACE
    assert settings.qdrant.api_key is None


def test_empty_qdrant_api_key_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QDRANT_API_KEY", "")
    settings = ServerSettings()
    assert settings.qdrant.api_key is None


def test_server_bind_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "9000")
    settings = ServerSettings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000


def test_server_settings_accepts_field_names() -> None:
    settings = ServerSettings(host="0.0.0.0", port=9000)
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000


def test_mcp_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENHEDGE_API_URL", "http://api:8000")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "8001")
    settings = McpServerSettings()
    assert settings.api_url == "http://api:8000"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8001


def test_sync_markets_settings_requires_openrouter_api_key() -> None:
    with pytest.raises(ValidationError):
        SyncMarketsSettings()


def test_sync_markets_settings_reads_openrouter_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    settings = SyncMarketsSettings()
    assert settings.openrouter.api_key == "sk-test"
    assert settings.batch_size == 100
    assert settings.qdrant.collection == DEFAULT_QDRANT_COLLECTION
    assert settings.qdrant.point_id_namespace == DEFAULT_POINT_ID_NAMESPACE
    assert settings.openrouter.embedding_model == DEFAULT_EMBEDDING_MODEL


def test_sync_markets_settings_reads_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("BATCH_SIZE", "50")
    settings = SyncMarketsSettings()
    assert settings.batch_size == 50
