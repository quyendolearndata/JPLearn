from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from jplearn_api.application.read_models import CatalogItemPublicDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.collection import CollectionDetail, PersonalCollection
from jplearn_api.domain.content import ContentVersion
from jplearn_api.domain.content_job import (
    ContentJob,
    ContentJobTask,
)
from jplearn_api.domain.content_report import (
    ContentReport,
    ContentReportAudit,
)
from jplearn_api.domain.identity import UserAccount
from jplearn_api.domain.learning import LearnerProgress, LearningSession
from jplearn_api.domain.media import MediaAsset
from jplearn_api.domain.playback import (
    HistoryDeletionJob,
    LearnerDailyActivity,
    LearnerPlaybackState,
    LearningPreferences,
    PlaybackCheckpoint,
    PlaybackReceipt,
    PlaybackSession,
    WatchHistoryItemProjection,
)
from jplearn_api.domain.quota import (
    AiUsageLedgerEntry,
    QuotaAccount,
)
from jplearn_api.domain.saved_scene import SavedScene
from jplearn_api.domain.series import Series
from jplearn_api.domain.transcript import (
    ApprovedSceneText,
    LanguageAnalysisJob,
    TranscriptRevision,
)


class FlagsRepository(Protocol):
    """Port for reading and updating feature flags."""

    async def get_flags(self) -> dict[str, bool]:
        """Fetch current feature flags mapping."""
        ...

    async def update_flags(self, flags: dict[str, bool]) -> dict[str, bool]:
        """Upsert feature flags mapping and return updated values."""
        ...

    async def ensure_defaults(self) -> None:
        """Ensure all default feature flags exist."""
        ...


class UserRepository(Protocol):
    """Port for user persistence and role management."""

    async def get_by_id(self, user_id: str) -> UserAccount | None: ...

    async def get_by_email(self, email: str) -> UserAccount | None: ...

    async def add(self, user: UserAccount) -> None: ...

    async def update(self, user: UserAccount) -> None: ...

    async def add_role(self, user_id: str, role: str) -> None: ...

    async def add_initial_progress(self, user_id: str, now: datetime) -> None: ...


class UpdateDraftResultStatus(StrEnum):
    UPDATED = "updated"
    NOT_FOUND = "not_found"
    WRONG_STATUS = "wrong_status"
    REVISION_CONFLICT = "revision_conflict"


@dataclass(frozen=True)
class UpdateDraftResult:
    status: UpdateDraftResultStatus
    item: CatalogItem | None = None


class CatalogRepository(Protocol):
    """Port for loading and persisting CatalogItem aggregates."""

    async def get_by_id(self, item_id: str) -> CatalogItem | None: ...

    async def get_by_id_for_update(self, item_id: str) -> CatalogItem | None:
        """Lock row with SELECT FOR UPDATE to serialize state transitions."""
        ...

    async def add(self, item: CatalogItem) -> None: ...

    async def update(self, item: CatalogItem) -> None: ...

    async def update_draft_cas(
        self,
        item_id: str,
        expected_revision: int,
        topic_id: str | None = None,
        ci_level: int | None = None,
        duration_seconds: int | None = None,
        media_type: str | None = None,
        visual_support: str | None = None,
        title_internal: str | None = None,
    ) -> UpdateDraftResult:
        """Atomically update a draft item with compare-and-swap on revision."""
        ...

    async def topic_exists(self, topic_id: str) -> bool: ...

    async def list_staff(
        self,
        status: str | None = None,
        ci_level: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogItem]: ...

    async def list_published(
        self,
        ci_level: int | None = None,
        topic_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CatalogItem]: ...


class CatalogQueryPort(Protocol):
    """Port for reading published catalog items."""

    async def list_published(self, ci_level: int | None) -> list[CatalogItemPublicDTO]: ...


class LearningRepository(Protocol):
    """Port for session and progress persistence with row-locking support."""

    async def acquire_idempotency_lock(self, user_id: str, key: str) -> None:
        """Acquire transaction-scoped advisory lock on (user_id, idempotency_key)."""
        ...

    async def create_session(self, session: LearningSession) -> None: ...

    async def get_session(self, session_id: str) -> LearningSession | None: ...

    async def lock_and_get_session(self, session_id: str) -> LearningSession | None: ...

    async def update_session(self, session: LearningSession) -> None: ...

    async def get_idempotency_session(self, user_id: str, key: str) -> tuple[str, str] | None: ...

    async def save_idempotency(self, user_id: str, key: str, session_id: str, request_hash: str) -> None: ...

    async def upsert_device(self, user_id: str, device_class: str, last_seen_at: datetime) -> None: ...

    async def get_progress(self, user_id: str) -> LearnerProgress | None: ...

    async def lock_and_get_progress(self, user_id: str) -> LearnerProgress | None: ...

    async def update_progress(self, progress: LearnerProgress) -> None: ...

    async def record_event(
        self,
        user_id: str,
        session_id: str | None,
        event_type: str,
        payload: dict,
        created_at: datetime,
    ) -> None: ...


class MediaRepository(Protocol):
    """Port for loading and persisting media asset metadata."""

    async def get_by_id(self, asset_id: str) -> MediaAsset | None: ...

    async def add(self, asset: MediaAsset) -> None: ...

    async def update(self, asset: MediaAsset) -> None: ...

    async def catalog_item_exists(self, catalog_item_id: str) -> bool: ...

    async def get_catalog_item_status(self, catalog_item_id: str, *, for_update: bool = False) -> str | None: ...

    async def list_all_storage_keys(self) -> set[str]: ...

    async def storage_key_exists(self, storage_key: str) -> bool: ...


class ContentRepository(Protocol):
    """Port for loading and persisting content versions and scene breakdowns."""

    async def is_media_pinned(self, asset_id: str) -> bool: ...

    async def get_published_by_catalog_item_id(self, catalog_item_id: str) -> ContentVersion | None: ...

    async def get_current_draft_by_catalog_item_id(self, catalog_item_id: str) -> ContentVersion | None: ...

    async def get_by_id(self, version_id: str) -> ContentVersion | None: ...

    async def save_draft(self, content_version: ContentVersion) -> None: ...

    async def update(self, content_version: ContentVersion) -> None: ...

    async def get_max_version_number(self, catalog_item_id: str) -> int: ...


class SeriesRepository(Protocol):
    """Port for loading and persisting Series aggregates."""

    async def get_by_id(self, series_id: str) -> Series | None: ...

    async def get_by_id_for_update(self, series_id: str) -> Series | None: ...

    async def add(self, series: Series) -> None: ...

    async def update(self, series: Series) -> None: ...

    async def list_staff(
        self,
        status: str | None = None,
        ci_level: str | None = None,
        topic_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Series]: ...

    async def list_published(
        self,
        ci_level: str | None = None,
        topic_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Series]: ...

    async def get_published_catalog_item_ids(self, item_ids: list[str]) -> set[str]: ...


class SavedSceneContext:
    def __init__(
        self,
        scene_id: str,
        content_version_id: str,
        is_version_published: bool,
        catalog_item_id: str,
        catalog_status: str,
        is_current_published_version: bool,
    ) -> None:
        self.scene_id = scene_id
        self.content_version_id = content_version_id
        self.is_version_published = is_version_published
        self.catalog_item_id = catalog_item_id
        self.catalog_status = catalog_status
        self.is_current_published_version = is_current_published_version


class SavedSceneProjection:
    def __init__(
        self,
        id: str,
        scene_id: str,
        saved_at: datetime,
        availability: str,
        unavailable_reason: str | None = None,
        catalog_item_id: str | None = None,
        content_version_id: str | None = None,
        scene_index: int | None = None,
        start_time_seconds: int | None = None,
        end_time_seconds: int | None = None,
        title_jp: str | None = None,
        transcript_jp: str | None = None,
    ) -> None:
        self.id = id
        self.scene_id = scene_id
        self.saved_at = saved_at
        self.availability = availability
        self.unavailable_reason = unavailable_reason
        self.catalog_item_id = catalog_item_id
        self.content_version_id = content_version_id
        self.scene_index = scene_index
        self.start_time_seconds = start_time_seconds
        self.end_time_seconds = end_time_seconds
        self.title_jp = title_jp
        self.transcript_jp = transcript_jp


class SavedSceneRepository(Protocol):
    """Port for loading and persisting saved scenes (bookmarks)."""

    async def get(self, user_id: str, scene_id: str) -> SavedScene | None: ...

    async def add(self, saved_scene: SavedScene) -> None: ...

    async def delete(self, user_id: str, scene_id: str) -> bool: ...

    async def get_scene_context(self, scene_id: str) -> SavedSceneContext | None: ...

    async def list_projections_by_user(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[SavedSceneProjection], int]: ...


class CollectionRepository(Protocol):
    """Port for loading and persisting personal collections."""

    async def acquire_library_lock(self, user_id: str) -> None:
        """Acquire row lock on learner_library_state for user_id to serialize library operations."""
        ...

    async def get_by_id(self, user_id: str, collection_id: str) -> PersonalCollection | None: ...

    async def get_detail(self, user_id: str, collection_id: str) -> CollectionDetail | None: ...

    async def find_by_idempotency_key(self, user_id: str, key: str) -> tuple[PersonalCollection, str | None] | None: ...

    async def count_by_user(self, user_id: str) -> int: ...

    async def create(
        self,
        collection: PersonalCollection,
        idempotency_key: str | None = None,
        request_hash: str | None = None,
    ) -> PersonalCollection: ...

    async def list_by_user(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PersonalCollection], int]: ...

    async def update_name(
        self,
        user_id: str,
        collection_id: str,
        expected_revision: int,
        new_name: str,
    ) -> PersonalCollection: ...

    async def replace_scenes(
        self,
        user_id: str,
        collection_id: str,
        expected_revision: int,
        scene_ids: list[str],
    ) -> PersonalCollection: ...

    async def delete(self, user_id: str, collection_id: str) -> bool: ...

    async def bump_revisions_for_scenes(self, user_id: str, scene_ids: list[str]) -> list[str]: ...


class ContentReportRepository(Protocol):
    """Port for content reports and moderation audits."""

    async def get_by_id(self, report_id: str) -> ContentReport | None: ...

    async def get_by_id_for_user(self, user_id: str, report_id: str) -> ContentReport | None: ...

    async def find_by_idempotency_key(
        self, user_id: str, idempotency_key: str
    ) -> tuple[ContentReport, str | None] | None: ...

    async def count_today_by_user(self, user_id: str, start_of_day: datetime) -> int:
        """Count reports submitted by user since start_of_day (UTC)."""
        ...

    async def create(
        self,
        report: ContentReport,
        request_hash: str | None = None,
    ) -> ContentReport: ...

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentReport], int]: ...

    async def list_staff(
        self,
        status: str | None = None,
        category: str | None = None,
        catalog_item_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentReport], int]: ...

    async def get_audit_logs(self, report_id: str) -> list[ContentReportAudit]: ...

    async def update_moderation(
        self,
        report_id: str,
        expected_revision: int,
        status: str | None = None,
        assignee_id: str | None = None,
        public_reply: str | None = None,
        internal_note: str | None = None,
        resolution_version_id: str | None = None,
        audit_actor_id: str | None = None,
        audit_reason: str | None = None,
    ) -> ContentReport: ...


class PlaybackRepository(Protocol):
    """Port for playback sessions, checkpoints, receipts, lease states, and daily activity."""

    async def acquire_learner_playback_lock(
        self,
        user_id: str,
        device_class: str,
        client_instance_id: str,
    ) -> LearnerPlaybackState:
        """Lock learner_playback_state row FOR UPDATE, initializing default if not present."""
        ...

    async def update_learner_playback_state(self, state: LearnerPlaybackState) -> None: ...

    async def get_playback(self, playback_id: str) -> PlaybackSession | None: ...

    async def create_playback(self, session: PlaybackSession) -> PlaybackSession: ...

    async def update_playback(self, session: PlaybackSession) -> None: ...

    async def get_receipt(self, playback_id: str, seq: int) -> PlaybackReceipt | None: ...

    async def save_receipt(self, receipt: PlaybackReceipt) -> None: ...

    async def get_checkpoint(self, user_id: str, catalog_item_id: str) -> PlaybackCheckpoint | None: ...

    async def save_checkpoint(self, checkpoint: PlaybackCheckpoint) -> None: ...

    async def list_resume(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PlaybackCheckpoint], int]: ...

    async def get_start_receipt(self, user_id: str, key: str) -> dict | None: ...

    async def save_start_receipt(self, user_id: str, key: str, request_hash: str, response: dict) -> None: ...

    async def get_learning_preferences(self, user_id: str) -> LearningPreferences:
        """Fetch preferences, returning default (15 mins, Asia/Ho_Chi_Minh) if not configured."""
        ...

    async def get_effective_learning_preferences(self, user_id: str, at: datetime) -> LearningPreferences: ...

    async def save_preference_version(self, pref: LearningPreferences) -> None: ...

    async def save_learning_preferences(self, pref: LearningPreferences) -> None: ...

    async def record_daily_active_ms(
        self,
        user_id: str,
        date_str: str,
        timezone_str: str,
        delta_ms: int,
        goal_minutes: int,
        policy_revision: int = 1,
    ) -> LearnerDailyActivity:
        """Atomically increment active_ms for the day and evaluate goal_met."""
        ...

    async def get_daily_activity_range(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
    ) -> list[LearnerDailyActivity]:
        """Fetch daily activity aggregates in [from_date, to_date] range."""
        ...

    async def get_latest_history_deletion_cutoff(self, user_id: str) -> datetime | None:
        """Return the most recent cutoff timestamp from active or completed deletion jobs."""
        ...

    async def list_watch_history(
        self,
        user_id: str,
        cutoff_time: datetime | None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[WatchHistoryItemProjection], str | None]:
        """List learner playback history excluding items before deletion cutoff."""
        ...

    async def create_history_deletion_job(self, job: HistoryDeletionJob) -> HistoryDeletionJob:
        """Enqueue a new history deletion request."""
        ...

    async def get_history_deletion_job(self, job_id: str) -> HistoryDeletionJob | None:
        """Fetch a specific deletion job by ID."""
        ...

    async def claim_next_history_deletion_job(self) -> HistoryDeletionJob | None:
        """Claim the next queued or retryable deletion job using FOR UPDATE SKIP LOCKED."""
        ...

    async def update_history_deletion_job(self, job: HistoryDeletionJob) -> None:
        """Update job status, attempts, error, or completion time."""
        ...

    async def purge_watch_history_before_cutoff(self, user_id: str, cutoff_time: datetime) -> int:
        """Hard delete playbacks, receipts, and resume checkpoints before cutoff."""
        ...


class TranscriptRepository(Protocol):
    """Port for loading and persisting transcript revisions, approved scenes, and language analysis."""

    async def get_latest_revision(
        self,
        catalog_item_id: str,
        content_version_id: str,
    ) -> TranscriptRevision | None:
        """Get latest revision of transcript for a given content version."""
        ...

    async def get_revision_by_id(
        self,
        revision_id: str,
    ) -> TranscriptRevision | None:
        """Get transcript revision by ID."""
        ...

    async def get_by_revision(
        self,
        catalog_item_id: str,
        content_version_id: str,
        revision: int,
    ) -> TranscriptRevision | None:
        """Get a specific revision of transcript."""
        ...

    async def save_revision(
        self,
        revision: TranscriptRevision,
        expected_revision: int | None = None,
    ) -> TranscriptRevision:
        """Save a new or updated transcript revision with optional atomic CAS verification."""
        ...

    async def activate_approved_scene_texts(
        self,
        catalog_item_id: str,
        content_version_id: str,
        transcript_revision_id: str,
        texts: list[ApprovedSceneText],
    ) -> None:
        """Atomically deactivate old approved texts and activate new approved texts for this version."""
        ...

    async def deactivate_approved_scene_texts(
        self,
        catalog_item_id: str,
        content_version_id: str,
    ) -> None:
        """Deactivate approved texts when a transcript is returned to draft."""
        ...

    async def create_language_analysis_job(
        self,
        job: LanguageAnalysisJob,
    ) -> LanguageAnalysisJob:
        """Create a language analysis job."""
        ...

    async def get_language_analysis_job(
        self,
        job_id: str,
    ) -> LanguageAnalysisJob | None:
        """Fetch a language analysis job by id."""
        ...

    async def get_language_analysis_job_by_idempotency_key(
        self,
        catalog_item_id: str,
        idempotency_key: str,
    ) -> LanguageAnalysisJob | None:
        """Fetch existing job with the same idempotency key."""
        ...

    async def search_approved_scenes(
        self,
        q: str,
        effective_max_ci: int,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[ApprovedSceneSearchResult], str | None, int]:
        """Search approved scene texts with exact phrase and token matching."""
        ...


@dataclass(frozen=True)
class ApprovedSceneSearchResult:
    catalog_item_id: str
    content_version_id: str
    scene_id: str
    scene_index: int
    start_time_seconds: int
    end_time_seconds: int
    matched_text_ja: str
    highlight_spans: list[dict[str, int]]
    match_kind: str
    ci_level: int
    topic_id: str
    title_jp: str


class QuotaRepository(Protocol):
    """Port for loading, locking and persisting AI quota accounts."""

    async def get_or_create_account_for_user(
        self,
        user_id: str,
        name: str = "Staff Default Quota",
    ) -> QuotaAccount:
        """Fetch or create default quota account for user."""
        ...

    async def get_by_id(
        self,
        account_id: str,
        for_update: bool = False,
    ) -> QuotaAccount | None:
        """Fetch quota account by ID, optionally acquiring a row-level lock."""
        ...

    async def save_account(
        self,
        account: QuotaAccount,
    ) -> None:
        """Persist updated quota account."""
        ...


class UsageLedgerRepository(Protocol):
    """Port for recording, deduping and querying AI usage ledger entries."""

    async def add_entry(
        self,
        entry: AiUsageLedgerEntry,
    ) -> None:
        """Append an entry to the usage ledger."""
        ...

    async def get_entry_by_id(
        self,
        entry_id: str,
    ) -> AiUsageLedgerEntry | None:
        """Get entry by primary key."""
        ...

    async def get_by_idempotency_key(
        self,
        account_id: str,
        idempotency_key: str,
        kind: str,
    ) -> AiUsageLedgerEntry | None:
        """Fetch entry by account, idempotency key and kind to prevent duplicate reservation."""
        ...

    async def get_reservation_by_job_id(
        self,
        job_id: str,
    ) -> AiUsageLedgerEntry | None:
        """Fetch reservation ledger entry by associated job ID."""
        ...

    async def get_settlement(
        self,
        provider: str,
        provider_request_id: str,
        attempt: int,
        kind: str = "settlement",
    ) -> AiUsageLedgerEntry | None:
        """Fetch settlement by provider request tuple to prevent duplicate settlement."""
        ...

    async def list_user_usage(
        self,
        user_id: str,
        from_date: datetime,
        to_date: datetime,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AiUsageLedgerEntry], int]:
        """List usage entries for a staff user within date range."""
        ...

    async def get_summary(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get aggregated usage summary across all accounts within date range."""
        ...


class ContentJobRepository(Protocol):
    """Port for persisting and claiming durable content jobs."""

    async def add(self, job: ContentJob) -> None:
        """Add a new content job to the queue."""
        ...

    async def get_by_id(self, job_id: str) -> ContentJob | None:
        """Retrieve content job by its primary key."""
        ...

    async def get_by_idempotency_key(
        self,
        created_by: str,
        idempotency_key: str,
    ) -> ContentJob | None:
        """Retrieve content job by creator and idempotency key."""
        ...

    async def find_active_job(
        self,
        content_version_id: str,
        task: ContentJobTask,
    ) -> ContentJob | None:
        """Find active (queued or running) job for a content version and task."""
        ...

    async def claim_next_queued_job(
        self,
        now: datetime,
        lease_duration_seconds: float,
        attempt_token: str,
    ) -> ContentJob | None:
        """Atomically claim the next eligible job with row-level lock."""
        ...

    async def update(self, job: ContentJob) -> None:
        """Update job state, lease, result or status."""
        ...

    async def save_attempt(self, attempt) -> None: ...

    async def get_attempt(self, attempt_id: str, for_update: bool = False): ...

    async def list_expired_attempts(self, now: datetime, limit: int = 100) -> list[str]: ...

    async def list_job_attempts(self, job_id: str): ...
