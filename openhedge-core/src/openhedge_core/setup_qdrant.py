import asyncio
import logging

import tenacity
from qdrant_client import AsyncQdrantClient

from openhedge_core.settings import SetupQdrantSettings
from openhedge_core.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

RETRY_STOP_AFTER_ATTEMPT = 8
RETRY_WAIT_MULTIPLIER = 1
RETRY_WAIT_MIN = 2
RETRY_WAIT_MAX = 16


@tenacity.retry(
    stop=tenacity.stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
    wait=tenacity.wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def setup_collection(settings: SetupQdrantSettings) -> None:
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


async def async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await setup_collection(SetupQdrantSettings())


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
