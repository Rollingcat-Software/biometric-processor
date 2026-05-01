"""Domain port for offloading blocking calls to a thread pool.

A minimal Protocol so infrastructure components can request a
`run_blocking(func, *args, **kwargs) -> awaitable T` adapter without
importing from `app.core.container`. Eliminates the infrastructure→
container coupling that Copilot flagged on PR #59 and makes
QualityAssessor / friends trivially unit-testable: a fake executor
that calls the function synchronously is a 4-line stub.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, TypeVar

T = TypeVar("T")


class IThreadPoolExecutorPort(Protocol):
    """Awaitable run_blocking-style executor port.

    Concrete implementations include `ThreadPoolManager` (production,
    in `app.infrastructure.async_execution`) and any synchronous test
    double that satisfies the same shape.
    """

    def run_blocking(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> Awaitable[T]:
        """Execute a blocking callable off the event loop and return its result."""
        ...
