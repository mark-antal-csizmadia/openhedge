import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Consumer(Generic[T]):
    def __init__(
        self,
        *,
        name: str,
        consume_fn: Callable[[list[T]], Awaitable[None]],
        queue: asyncio.Queue[T],
        shutdown_event: asyncio.Event,
        batch_size: int = 64,
        producers_done: asyncio.Event | None = None,
    ):
        self._name = name
        self._consume_fn = consume_fn
        self._queue = queue
        self._shutdown_event = shutdown_event
        self._running = False
        self._batch_size = batch_size
        self._producers_done = producers_done

    async def run(self) -> None:
        batch: list[T] = []
        self._running = True
        try:
            while self._running and not self._shutdown_event.is_set():
                got_item = False
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                    got_item = True
                except asyncio.TimeoutError:
                    pass

                if got_item:
                    batch.append(item)

                should_flush = (
                    len(batch) >= self._batch_size
                    or (not got_item and batch)
                    or (self._shutdown_event.is_set() and batch)
                )
                if should_flush:
                    await self._consume_fn(batch)
                    batch = []

                if (
                    self._producers_done is not None
                    and self._producers_done.is_set()
                    and self._queue.empty()
                    and not batch
                ):
                    break

            if batch:
                await self._consume_fn(batch)
                batch = []
        except asyncio.CancelledError:
            logger.info("Consumer %s cancelled", self._name)
            raise
        except Exception:
            logger.exception("Consumer %s error", self._name)
            raise
        finally:
            self._running = False
            logger.info("Consumer %s stopped", self._name)

    async def stop(self) -> None:
        self._running = False
        self._shutdown_event.set()
