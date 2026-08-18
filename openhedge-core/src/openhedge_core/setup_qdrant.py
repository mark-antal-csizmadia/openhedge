import asyncio
import logging

from qdrant_client import AsyncQdrantClient

from openhedge_core.settings import SetupQdrantSettings
from openhedge_core.vector_store import QdrantVectorStore


async def async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = SetupQdrantSettings()
    qdrant = AsyncQdrantClient(
        url=settings.qdrant.url,
        api_key=settings.qdrant.api_key,
    )
    try:
        store = QdrantVectorStore(
            qdrant,
            collection=settings.qdrant.collection,
            point_id_namespace=settings.qdrant.point_id_namespace,
        )
        await store.setup(vector_size=settings.openrouter.embedding_dim)
    finally:
        await qdrant.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
