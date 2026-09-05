"""SQLAlchemy Unit of Work adapter."""

from __future__ import annotations

from types import TracebackType
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork


class SqlAlchemyUnitOfWork(AsyncUnitOfWork):
    """SQLAlchemy implementation of AsyncUnitOfWork with rollback-by-default."""

    def __init__(
        self,
        session_factory_or_session: async_sessionmaker[AsyncSession] | AsyncSession,
    ) -> None:
        if isinstance(session_factory_or_session, AsyncSession):
            self._session_factory = None
            self.session = session_factory_or_session
            self._managed_session = False
        else:
            self._session_factory = session_factory_or_session
            self.session = None  # type: ignore[assignment]
            self._managed_session = True
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        if self._managed_session and self._session_factory is not None:
            self.session = self._session_factory()
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None or not self._committed:
                await self.rollback()
        finally:
            if self._managed_session and self.session is not None:
                await self.session.close()

    async def commit(self) -> None:
        """Commit the current transaction explicitly."""
        if self.session is not None:
            await self.session.commit()
            self._committed = True

    async def rollback(self) -> None:
        """Roll back pending changes."""
        if self.session is not None:
            await self.session.rollback()


def create_uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Create a factory yielding fresh SqlAlchemyUnitOfWork instances."""
    return lambda: SqlAlchemyUnitOfWork(session_factory)
