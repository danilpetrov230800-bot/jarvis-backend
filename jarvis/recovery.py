from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")

_failures: dict[str, int] = {}
_restarted_at: dict[str, float] = {}


def mark_ok(component: str) -> None:
    _failures[component] = 0


def mark_fail(component: str) -> int:
    _failures[component] = _failures.get(component, 0) + 1
    _restarted_at[component] = time.monotonic()
    log.warning("component %s failed (%s)", component, _failures[component])
    return _failures[component]


async def retry_async(component: str, fn: Callable[[], Awaitable[T]], attempts: int = 2) -> T:
    last: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            value = await fn()
            mark_ok(component)
            return value
        except Exception as exc:  # noqa: BLE001
            last = exc
            mark_fail(component)
    assert last is not None
    raise last


def status() -> dict[str, int]:
    return dict(_failures)
