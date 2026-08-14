import asyncio
import logging
import os

from qdrant_client import AsyncQdrantClient

from openhedge_core.embeddings import EMBEDDING_DIM
from openhedge_core.vector_store import DEFAULT_QDRANT_COLLECTION, DEFAULT_QDRANT_URL, QdrantVectorStore


async def async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    dimensions = int(os.environ.get("OPENROUTER_EMBEDDING_DIM", str(EMBEDDING_DIM)))
    qdrant = AsyncQdrantClient(
        url=os.environ.get("QDRANT_URL", DEFAULT_QDRANT_URL),
        api_key=os.environ.get("QDRANT_API_KEY") or None,
    )
    try:
        store = QdrantVectorStore(
            qdrant,
            collection=os.environ.get("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION),
        )
        await store.setup(vector_size=dimensions)
    finally:
        await qdrant.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
