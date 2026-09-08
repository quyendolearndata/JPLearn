"""SQLAlchemy Unit of Work adapter."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from types import TracebackType
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jplearn_api.adapters.persistence.catalog_repository import SqlAlchemyCatalogRepository
from jplearn_api.adapters.persistence.collection_repository import SqlAlchemyCollectionRepository
from jplearn_api.adapters.persistence.content_job_repository import SqlAlchemyContentJobRepository
from jplearn_api.adapters.persistence.content_report_repository import SqlAlchemyContentReportRepository
from jplearn_api.adapters.persistence.content_repository import SqlAlchemyContentRepository
from jplearn_api.adapters.persistence.flags_repository import SqlAlchemyFlagsRepository
from jplearn_api.adapters.persistence.learning_repository import SqlAlchemyLearningRepository
from jplearn_api.adapters.persistence.media_repository import SqlAlchemyMediaRepository
from jplearn_api.adapters.persistence.playback_repository import SqlAlchemyPlaybackRepository
from jplearn_api.adapters.persistence.quota_repository import (
    SqlAlchemyQuotaRepository,
    SqlAlchemyUsageLedgerRepository,
)
from jplearn_api.adapters.persistence.saved_scene_repository import SqlAlchemySavedSceneRepository
from jplearn_api.adapters.persistence.series_repository import SqlAlchemySeriesRepository
from jplearn_api.adapters.persistence.transcript_repository import SqlAlchemyTranscriptRepository
from jplearn_api.adapters.persistence.user_repository import SqlAlchemyUserRepository
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.domain.errors import DeterministicAbortError

logger = logging.getLogger(__name__)
# Strong references retain quarantined scopes until settlement AND close finish.
_quarantined: set[asyncio.Task[None]] = set()


async def drain_quarantined_scopes(timeout: float = 5.0) -> None:
    tasks = {t for t in _quarantined if t.get_loop() is asyncio.get_running_loop()}
    if tasks:
        _, pending = await asyncio.wait(tasks, timeout=timeout)
        if pending:
            logger.error("uow_shutdown_cleanup_pending", extra={"pending_count": len(pending)})
            raise RuntimeError("Pending UoW cleanup: refuse concurrent engine/storage disposal")


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
            self.content = None  # type: ignore[assignment]
            self.media = None  # type: ignore[assignment]
            self.learning = None  # type: ignore[assignment]
            self.flags = None  # type: ignore[assignment]
            self.series = None  # type: ignore[assignment]
            self.saved_scenes = None  # type: ignore[assignment]
            self.collections = None  # type: ignore[assignment]
            self.content_reports = None  # type: ignore[assignment]
            self.playbacks = None  # type: ignore[assignment]
            self.transcripts = None  # type: ignore[assignment]
            self.quota = None  # type: ignore[assignment]
            self.usage_ledger = None  # type: ignore[assignment]
            self.content_jobs = None  # type: ignore[assignment]
        self._committed = False
        self._rolled_back = False
        self._cleanup: asyncio.Task[None] | None = None
        self._depth = 0

    def own_cleanup(self, task: asyncio.Task[None]) -> None:
        self._cleanup = task

    def _bind_repositories(self, session: AsyncSession) -> None:
        self.users = SqlAlchemyUserRepository(session)
        self.catalog = SqlAlchemyCatalogRepository(session)
        self.content = SqlAlchemyContentRepository(session)
        self.media = SqlAlchemyMediaRepository(session)
        self.learning = SqlAlchemyLearningRepository(session)
        self.flags = SqlAlchemyFlagsRepository(session)
        self.series = SqlAlchemySeriesRepository(session)
        self.saved_scenes = SqlAlchemySavedSceneRepository(session)
        self.collections = SqlAlchemyCollectionRepository(session)
        self.content_reports = SqlAlchemyContentReportRepository(session)
        self.playbacks = SqlAlchemyPlaybackRepository(session)
        self.transcripts = SqlAlchemyTranscriptRepository(session)
        self.quota = SqlAlchemyQuotaRepository(session)
        self.usage_ledger = SqlAlchemyUsageLedgerRepository(session)
        self.content_jobs = SqlAlchemyContentJobRepository(session)

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._depth += 1
        if self._depth > 1:
            return self
        if any(t.get_loop() is asyncio.get_running_loop() for t in _quarantined):
            raise RuntimeError("UoW cleanup quarantined; new transaction admission suspended")
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
        self._depth -= 1
        if self._depth > 0:
            if exc_type is not None and not self._rolled_back:
                await self.rollback()
            return
        if self._cleanup is not None:

            async def finish() -> None:
                try:
                    await self._cleanup
                except BaseException as error:
                    logger.warning("uow_cleanup_incomplete", extra={"reason": type(error).__name__})
                finally:
                    if self._managed_session and self.session is not None:
                        await self.session.close()

            # This task alone owns close. Request cancellation cannot race it.
            task = asyncio.create_task(finish())
            _quarantined.add(task)

            def observed(done: asyncio.Task[None]) -> None:
                _quarantined.discard(done)
                if not done.cancelled() and done.exception() is not None:
                    logger.error("uow_deferred_close_failed", extra={"reason": type(done.exception()).__name__})

            task.add_done_callback(observed)
            if self._cleanup.done():
                deadline = asyncio.get_running_loop().time() + 5.0
                while not task.done():
                    try:
                        remaining = deadline - asyncio.get_running_loop().time()
                        if remaining <= 0:
                            logger.warning("uow_close_quarantined")
                            break
                        await asyncio.wait_for(asyncio.shield(task), remaining)
                    except TimeoutError:
                        logger.warning("uow_close_quarantined")
                        break
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        if exc_type is None:
                            raise
                        break  # done callback reports close failure; preserve original error
            return
        try:
            if (exc_type is not None or not self._committed) and not self._rolled_back:
                await self.rollback()
        except Exception:
            if exc_type is None:
                raise
        finally:
            if self._managed_session and self.session is not None:
                await self.session.close()

    @property
    def committed(self) -> bool:
        return self._committed

    @property
    def rolled_back(self) -> bool:
        return self._rolled_back

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
        if self.session is not None:
            await self.session.rollback()
        self._rolled_back = True


def create_uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Create a factory yielding fresh SqlAlchemyUnitOfWork instances."""
    return lambda: SqlAlchemyUnitOfWork(session_factory)
