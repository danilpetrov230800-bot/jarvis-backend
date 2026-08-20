from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Coroutine

from nova.logging_service import LogService


class Supervisor:
    """Restart a failed subsystem without restarting the whole app."""

    def __init__(self, log: LogService) -> None:
        self.log = log
        self._stop = threading.Event()
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def stop(self) -> None:
        self._stop.set()
        for task in list(self._tasks.values()):
            task.cancel()

    async def watch(
        self,
        name: str,
        factory: Callable[[], Coroutine[Any, Any, Any]],
        *,
        retries: int = 5,
        delay: float = 1.5,
    ) -> None:
        attempt = 0
        while not self._stop.is_set() and attempt <= retries:
            try:
                await factory()
                return
            except asyncio.CancelledError:
                return
            except Exception as exc:
                attempt += 1
                self.log.error(f"{name} crashed, restarting", detail=str(exc), attempt=attempt)
                await asyncio.sleep(min(delay * attempt, 8))
        self.log.warning(f"{name} disabled after repeated failures")
