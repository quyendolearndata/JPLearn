"""Application commands (Pure Python dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateFlagsCommand:
    flags: dict[str, bool]


@dataclass(frozen=True)
class RegisterUserCommand:
    email: str
    password: str
    secret: str


@dataclass(frozen=True)
class LogoutUserCommand:
    user_id: str


@dataclass(frozen=True)
class CreateCatalogItemCommand:
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    visual_support: str
    title_internal: str
    created_by: str


@dataclass(frozen=True)
class SubmitCatalogForQaCommand:
    item_id: str


@dataclass(frozen=True)
class PublishCatalogItemCommand:
    item_id: str


@dataclass(frozen=True)
class UnpublishCatalogItemCommand:
    item_id: str


@dataclass(frozen=True)
class ArchiveCatalogItemCommand:
    item_id: str


@dataclass(frozen=True)
class StartLearningSessionCommand:
    user_id: str
    device_class: str
    idempotency_key: str | None = None
    request_hash: str | None = None


@dataclass(frozen=True)
class EndLearningSessionCommand:
    user_id: str
    session_id: str


@dataclass(frozen=True)
class UpdateDraftCatalogItemCommand:
    item_id: str
    revision: int
    topic_id: str | None = None
    ci_level: int | None = None
    duration_seconds: int | None = None
    media_type: str | None = None
    visual_support: str | None = None
    title_internal: str | None = None


@dataclass(frozen=True)
class SceneInput:
    scene_index: int
    start_time_seconds: int
    end_time_seconds: int
    title_jp: str
    transcript_jp: str


@dataclass(frozen=True)
class UpdateContentDraftCommand:
    catalog_item_id: str
    version_revision: int
    scenes: list[SceneInput]


@dataclass(frozen=True)
class ReturnToDraftCommand:
    catalog_item_id: str


@dataclass(frozen=True)
class SaveSceneCommand:
    user_id: str
    scene_id: str


@dataclass(frozen=True)
class DeleteSavedSceneCommand:
    user_id: str
    scene_id: str


@dataclass(frozen=True)
class CreateCollectionCommand:
    user_id: str
    name: str
    idempotency_key: str | None = None


@dataclass(frozen=True)
class PatchCollectionCommand:
    user_id: str
    collection_id: str
    expected_revision: int
    name: str


@dataclass(frozen=True)
class UpdateCollectionScenesCommand:
    user_id: str
    collection_id: str
    expected_revision: int
    scene_ids: list[str]


@dataclass(frozen=True)
class DeleteCollectionCommand:
    user_id: str
    collection_id: str


@dataclass(frozen=True)
class CreateContentReportCommand:
    user_id: str
    catalog_item_id: str
    content_version_id: str
    category: str
    description: str
    scene_id: str | None = None
    position_ms: int = 0
    idempotency_key: str | None = None


@dataclass(frozen=True)
class PatchStaffContentReportCommand:
    report_id: str
    expected_revision: int
    actor_id: str
    status: str | None = None
    assignee_id: str | None = None
    public_reply: str | None = None
    internal_note: str | None = None
    resolution_version_id: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class StartPlaybackCommand:
    user_id: str
    catalog_item_id: str
    device_id: str
    device_info: dict[str, Any] | None = None
    take_over: bool = False
    idempotency_key: str | None = None
    content_version_id: str | None = None


@dataclass(frozen=True)
class SendCheckpointCommand:
    user_id: str
    playback_id: str
    seq: int
    position_ms: int
    duration_ms: int
    playback_rate: float
    state: str
    client_cumulative_active_ms: int
    client_epoch: int
    client_time: datetime | None = None
    scene_id: str | None = None


@dataclass(frozen=True)
class EndPlaybackCommand:
    user_id: str
    playback_id: str
    final_seq: int | None = None
    final_position_ms: int | None = None
    final_duration_ms: int | None = None
    final_playback_rate: float = 1.0
    final_client_cumulative_active_ms: int | None = None
    final_client_epoch: int | None = None
    final_scene_id: str | None = None


@dataclass(frozen=True)
class UpdateLearningPreferencesCommand:
    user_id: str
    expected_revision: int
    daily_goal_minutes: int | None = None
    preferred_topic_ids: list[str] | None = None
    timezone: str | None = None


@dataclass(frozen=True)
class RequestHistoryDeletionCommand:
    user_id: str


@dataclass(frozen=True)
class SaveTranscriptDraftCommand:
    user_id: str
    catalog_item_id: str
    content_version_id: str
    expected_revision: int
    segments: list[dict[str, str]]
    provenance: str = "manual_teacher"


@dataclass(frozen=True)
class SubmitTranscriptQACommand:
    user_id: str
    catalog_item_id: str
    content_version_id: str
    expected_revision: int


@dataclass(frozen=True)
class ApproveTranscriptCommand:
    user_id: str
    catalog_item_id: str
    content_version_id: str
    expected_revision: int


@dataclass(frozen=True)
class ReturnTranscriptToDraftCommand:
    user_id: str
    catalog_item_id: str
    content_version_id: str
    expected_revision: int
    reason: str


@dataclass(frozen=True)
class CreateLanguageAnalysisJobCommand:
    user_id: str
    catalog_item_id: str
    transcript_revision_id: str
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ReserveQuotaCommand:
    user_id: str
    job_id: str
    idempotency_key: str
    provider: str
    audio_seconds: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micros: int = 0
    currency: str = "USD"
    account_id: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class SettleUsageCommand:
    account_id: str
    reservation_entry_id: str
    actual_audio_seconds: int
    actual_input_tokens: int
    actual_output_tokens: int
    actual_cost_micros: int
    provider_request_id: str | None = None
    attempt: int = 1
    description: str | None = None


@dataclass(frozen=True)
class ReleaseQuotaCommand:
    account_id: str
    reservation_entry_id: str
    reason: str | None = None


@dataclass(frozen=True)
class ReconcileQuotaCommand:
    account_id: str
    reservation_entry_id: str
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class CreateContentJobCommand:
    catalog_item_id: str
    content_version_id: str
    task: str
    idempotency_key: str
    user_id: str
    language: str = "ja"
    estimated_audio_seconds: int = 300
    estimated_cost_micros: int = 500000


@dataclass(frozen=True)
class CancelContentJobCommand:
    job_id: str
    user_id: str
    user_roles: tuple[str, ...] = ("teacher",)


@dataclass(frozen=True)
class ApplyContentJobCommand:
    job_id: str
    expected_revision: int
    user_id: str
    segments: list[dict[str, str]] | None = None
