"""SQLAlchemy Unit of Work adapter."""

from __future__ import annotations

from types import TracebackType
from typing import Any, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jplearn_api.adapters.persistence.catalog_repository import SqlAlchemyCatalogRepository
from jplearn_api.adapters.persistence.flags_repository import SqlAlchemyFlagsRepository
from jplearn_api.adapters.persistence.learning_repository import SqlAlchemyLearningRepository
from jplearn_api.adapters.persistence.media_repository import SqlAlchemyMediaRepository
from jplearn_api.adapters.persistence.user_repository import SqlAlchemyUserRepository
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.domain.errors import DeterministicAbortError


class SqlAlchemyUnitOfWork(AsyncUnitOfWork):
    """SQLAlchemy implementation of AsyncUnitOfWork with rollback-by-default."""

    def __init__(
        self,
        session_factory_or_session: async_sessionmaker[AsyncSession] | AsyncSession | Any,
    ) -> None:
        if hasattr(session_factory_or_session, "commit"):
            self._session_factory = None
            self.session = session_factory_or_session
            self._managed_session = False
            self._bind_repositories(self.session)
        else:
            self._session_factory = session_factory_or_session
            self.session = None  # type: ignore[assignment]
            self._managed_session = True
            self.users = None  # type: ignore[assignment]
            self.catalog = None  # type: ignore[assignment]
            self.media = None  # type: ignore[assignment]
            self.learning = None  # type: ignore[assignment]
            self.flags = None  # type: ignore[assignment]
        self._committed = False
        self._rolled_back = False

    def _bind_repositories(self, session: AsyncSession) -> None:
        self.users = SqlAlchemyUserRepository(session)
        self.catalog = SqlAlchemyCatalogRepository(session)
        self.media = SqlAlchemyMediaRepository(session)
        self.learning = SqlAlchemyLearningRepository(session)
        self.flags = SqlAlchemyFlagsRepository(session)

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        if self._managed_session and self._session_factory is not None:
            self.session = self._session_factory()
            self._bind_repositories(self.session)
        self._committed = False
        self._rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if (exc_type is not None or not self._committed) and not self._rolled_back:
                await self.rollback()
        except Exception:
            if exc_type is None:
                raise
        finally:
            if self._managed_session and self.session is not None:
                await self.session.close()

    async def commit(self) -> None:
        """Commit the current transaction explicitly."""
        if self.session is not None:
            try:
                await self.session.commit()
                self._committed = True
            except IntegrityError as exc:
                raise DeterministicAbortError(str(exc)) from exc

    async def rollback(self) -> None:
        """Roll back pending changes."""
        self._rolled_back = True
        if self.session is not None:
            await self.session.rollback()


def create_uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Create a factory yielding fresh SqlAlchemyUnitOfWork instances."""
    return lambda: SqlAlchemyUnitOfWork(session_factory)
