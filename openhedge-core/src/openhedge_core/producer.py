import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Producer(Generic[T]):
    def __init__(
        self,
        *,
        name: str,
        produce_fn: Callable[[], AsyncIterator[T]],
        queue: asyncio.Queue[T],
        shutdown_event: asyncio.Event,
    ):
        self._name = name
        self._produce_fn = produce_fn
        self._queue = queue
        self._shutdown_event = shutdown_event
        self._running = False

    async def run(self) -> None:
        self._running = True
        try:
            async for item in self._produce_fn():
                if self._shutdown_event.is_set():
                    break
                put_task = asyncio.create_task(self._queue.put(item))
                shutdown_task = asyncio.create_task(self._shutdown_event.wait())
                done, _ = await asyncio.wait([put_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED)
                shutdown_task.cancel()
                if put_task not in done:
                    put_task.cancel()
                    break
                if self._shutdown_event.is_set():
                    break
        except asyncio.CancelledError:
            logger.info("Producer %s cancelled", self._name)
            raise
        except Exception:
            logger.exception("Error in producer %s", self._name)
            raise
        finally:
            self._running = False
            logger.info("Producer %s stopped", self._name)

    async def stop(self) -> None:
        self._running = False
        self._shutdown_event.set()
