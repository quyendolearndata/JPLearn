"""Unit of Work port (Pure Python, protocol-based)."""

from __future__ import annotations

import asyncio

from types import TracebackType
from typing import Callable, Protocol, TypeVar

from jplearn_api.application.ports.repositories import (
    CatalogRepository,
    CollectionRepository,
    ContentJobRepository,
    ContentReportRepository,
    ContentRepository,
    FlagsRepository,
    LearningRepository,
    MediaRepository,
    PlaybackRepository,
    QuotaRepository,
    SavedSceneRepository,
    SeriesRepository,
    TranscriptRepository,
    UsageLedgerRepository,
    UserRepository,
)

T = TypeVar("T", bound="AsyncUnitOfWork")


class AsyncUnitOfWork(Protocol):
    """Protocol for atomic transaction boundaries with rollback-by-default."""

    users: UserRepository
    catalog: CatalogRepository
    content: ContentRepository
    media: MediaRepository
    learning: LearningRepository
    flags: FlagsRepository
    series: SeriesRepository
    saved_scenes: SavedSceneRepository
    collections: CollectionRepository
    content_reports: ContentReportRepository
    playbacks: PlaybackRepository
    transcripts: TranscriptRepository
    quota: QuotaRepository
    usage_ledger: UsageLedgerRepository
    content_jobs: ContentJobRepository

    async def __aenter__(self: T) -> T:
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        ...

    committed: bool
    rolled_back: bool

    def own_cleanup(self, task: asyncio.Task[None]) -> None:
        """Own pending settlement; exit must not close resources before it ends."""
        ...

    async def commit(self) -> None:
        """Explicitly commit pending mutations."""
        ...

    async def rollback(self) -> None:
        """Roll back pending changes."""
        ...


UnitOfWorkFactory = Callable[[], AsyncUnitOfWork]
