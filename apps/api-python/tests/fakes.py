"""Test fakes for Clean Architecture unit testing (Zero external I/O)."""

from __future__ import annotations

from types import TracebackType

from jplearn_api.application.ports.repositories import FlagsRepository
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork


class FakeUnitOfWork(AsyncUnitOfWork):
    """In-memory Unit of Work recording commit/rollback actions."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeUnitOfWork:
        self.committed = False
        self.rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None or not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeFlagsRepository(FlagsRepository):
    """In-memory fake implementation of FlagsRepository."""

    def __init__(self, initial_flags: dict[str, bool] | None = None) -> None:
        self.flags: dict[str, bool] = {
            "speaking_enabled": False,
            "l1_subtitles_enabled": False,
            "grammar_enabled": False,
            "flashcards_enabled": False,
        }
        if initial_flags:
            self.flags.update(initial_flags)

    async def ensure_defaults(self) -> None:
        pass

    async def get_flags(self) -> dict[str, bool]:
        return dict(self.flags)

    async def update_flags(self, flags: dict[str, bool]) -> dict[str, bool]:
        self.flags.update(flags)
        return dict(self.flags)
