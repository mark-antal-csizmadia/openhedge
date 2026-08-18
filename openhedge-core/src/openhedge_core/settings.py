from typing import Self

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from openhedge_core.embeddings import DEFAULT_EMBEDDING_MODEL, EMBEDDING_DIM
from openhedge_core.vector_store import DEFAULT_QDRANT_COLLECTION, DEFAULT_QDRANT_URL

DEFAULT_OPENROUTER_HTTP_REFERER = "https://openhedge.dev"
DEFAULT_OPENROUTER_APP_TITLE = "openhedge"


class QdrantSettings(BaseModel):
    url: str = DEFAULT_QDRANT_URL
    api_key: str | None = None
    collection: str = DEFAULT_QDRANT_COLLECTION


class OpenRouterSettings(BaseModel):
    api_key: str | None = None
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_dim: int = EMBEDDING_DIM
    http_referer: str = DEFAULT_OPENROUTER_HTTP_REFERER
    app_title: str = DEFAULT_OPENROUTER_APP_TITLE


class RequiredOpenRouterSettings(OpenRouterSettings):
    api_key: str = Field(min_length=1)


class _ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="_",
        env_nested_max_split=1,
        env_ignore_empty=True,
        nested_model_default_partial_update=True,
        populate_by_name=True,
    )


class ServerSettings(_ServiceSettings):
    host: str = Field(default="127.0.0.1", validation_alias="API_HOST")
    port: int = Field(default=8000, validation_alias="API_PORT")
    qdrant: QdrantSettings = QdrantSettings()
    openrouter: OpenRouterSettings = OpenRouterSettings()


class McpServerSettings(_ServiceSettings):
    api_url: str = Field(default="http://127.0.0.1:8000", validation_alias="OPENHEDGE_API_URL")
    host: str = Field(default="127.0.0.1", validation_alias="MCP_HOST")
    port: int = Field(default=8001, validation_alias="MCP_PORT")


class SyncMarketsSettings(_ServiceSettings):
    qdrant: QdrantSettings = QdrantSettings()
    openrouter: RequiredOpenRouterSettings = Field(
        default_factory=lambda: RequiredOpenRouterSettings.model_construct(api_key=""),
    )

    @model_validator(mode="after")
    def require_openrouter_api_key(self) -> Self:
        if not self.openrouter.api_key:
            raise ValueError("OPENROUTER_API_KEY is required")
        return self


class SetupQdrantSettings(_ServiceSettings):
    qdrant: QdrantSettings = QdrantSettings()
    openrouter: OpenRouterSettings = OpenRouterSettings()
