"""Application queries (Pure Python dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GetFlagsQuery:
    pass


@dataclass(frozen=True)
class AuthenticateUserQuery:
    email: str
    password: str
    secret: str


@dataclass(frozen=True)
class GetCurrentUserQuery:
    user_id: str


@dataclass(frozen=True)
class ListPublishedCatalogQuery:
    ci_level: int | None = None


@dataclass(frozen=True)
class GetLearnerProgressQuery:
    user_id: str


@dataclass(frozen=True)
class GetSessionQuery:
    session_id: str
    user_id: str


@dataclass(frozen=True)
class ListStaffCatalogQuery:
    status: str | None = None
    ci_level: int | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetStaffCatalogItemQuery:
    item_id: str


@dataclass(frozen=True)
class GetPublishedContentQuery:
    catalog_item_id: str


@dataclass(frozen=True)
class GetStaffContentQuery:
    catalog_item_id: str


@dataclass(frozen=True)
class ListSavedScenesQuery:
    user_id: str
    offset: int = 0
    limit: int = 50


@dataclass(frozen=True)
class ListCollectionsQuery:
    user_id: str
    offset: int = 0
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True)
class GetCollectionQuery:
    user_id: str
    collection_id: str


@dataclass(frozen=True)
class ListMyContentReportsQuery:
    user_id: str
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetMyContentReportQuery:
    user_id: str
    report_id: str


@dataclass(frozen=True)
class ListStaffContentReportsQuery:
    status: str | None = None
    category: str | None = None
    catalog_item_id: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetStaffContentReportQuery:
    report_id: str


@dataclass(frozen=True)
class GetPlaybackQuery:
    user_id: str
    playback_id: str


@dataclass(frozen=True)
class ListResumeQuery:
    user_id: str
    offset: int = 0
    limit: int = 50


@dataclass(frozen=True)
class GetItemResumeQuery:
    user_id: str
    catalog_item_id: str


@dataclass(frozen=True)
class GetLearningPreferencesQuery:
    user_id: str


@dataclass(frozen=True)
class GetDailyActivityQuery:
    user_id: str
    from_date: str
    to_date: str


@dataclass(frozen=True)
class GetWatchHistoryQuery:
    user_id: str
    cursor: str | None = None
    limit: int = 50


@dataclass(frozen=True)
class GetHistoryDeletionQuery:
    user_id: str
    deletion_id: str


@dataclass(frozen=True)
class GetRecommendationsQuery:
    user_id: str
    limit: int = 10


@dataclass(frozen=True)
class GetTranscriptQuery:
    catalog_item_id: str
    content_version_id: str | None = None


@dataclass(frozen=True)
class GetLanguageAnalysisJobQuery:
    job_id: str


@dataclass(frozen=True)
class SearchScenesQuery:
    q: str
    user_id: str
    ci_level: int | None = None
    cursor: str | None = None
    limit: int = 20


@dataclass(frozen=True)
class GetMyAiUsageQuery:
    user_id: str
    from_date: datetime
    to_date: datetime
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetAiUsageSummaryQuery:
    from_date: datetime
    to_date: datetime


@dataclass(frozen=True)
class GetContentJobQuery:
    job_id: str
    user_id: str
    user_roles: tuple[str, ...] = ("teacher",)
