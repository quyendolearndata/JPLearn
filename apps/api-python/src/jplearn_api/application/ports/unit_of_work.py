"""Unit of Work port (Pure Python, protocol-based)."""

from __future__ import annotations

from types import TracebackType
from typing import Callable, Protocol, TypeVar

T = TypeVar("T", bound="AsyncUnitOfWork")


class AsyncUnitOfWork(Protocol):
    """Protocol for atomic transaction boundaries with rollback-by-default."""

    async def __aenter__(self: T) -> T:
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        ...

    async def commit(self) -> None:
        """Explicitly commit pending mutations."""
        ...

    async def rollback(self) -> None:
        """Roll back pending mutations."""
        ...


UnitOfWorkFactory = Callable[[], AsyncUnitOfWork]
