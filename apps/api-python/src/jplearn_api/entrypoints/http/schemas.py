from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

class RegisterBody(BaseModel):
    email: str = Field(json_schema_extra={"format": "email"})
    password: str = Field(json_schema_extra={"minLength": 10})

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v or "@" not in v:
            raise ValueError("Invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("Password must be at least 10 characters")
        return v


class LoginBody(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    email: str
    roles: list[Literal["learner", "teacher", "admin"]]


class AuthSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str
    user: UserPublic


class Flags(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speaking_enabled: bool
    l1_subtitles_enabled: bool
    grammar_enabled: bool
    flashcards_enabled: bool


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_scene_breakdown_enabled: bool
    smart_stream_enabled: bool
    interactive_dual_subs_enabled: bool
    immersion_lookup_enabled: bool
    personal_collections_enabled: bool
    content_reports_enabled: bool
    playback_tracking_enabled: bool
    scene_search_enabled: bool
    staff_ai_enabled: bool


class SceneWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_index: int
    start_time_seconds: int
    end_time_seconds: int
    title_jp: str
    transcript_jp: str


class ContentUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_revision: int
    scenes: list[SceneWrite]


class ScenePublic(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: str = Field(json_schema_extra={"format": "uuid"})
    scene_index: int
    start_time_seconds: int
    end_time_seconds: int
    title_jp: str


class SceneStaff(ScenePublic):
    transcript_jp: str


class ContentVersionPublic(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: str
    catalog_item_id: str = Field(json_schema_extra={"format": "uuid"})
    version_number: int
    revision: int
    is_frozen: bool
    is_published: bool
    scenes: list[ScenePublic]


class ContentVersionStaff(ContentVersionPublic):
    scenes: list[SceneStaff]


class CatalogItemWrite(BaseModel):
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: Literal["video", "audio"]
    visual_support: Literal["high", "medium", "low"]
    title_internal: str


class CatalogItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    ci_level: int
    duration_seconds: int
    media_type: Literal["video", "audio"]
    topic_id: str
    visual_support: Literal["high", "medium", "low"]
    playback_url: str | None = Field(default=None, json_schema_extra={"format": "uri"})
    hls_url: str | None = Field(default=None, json_schema_extra={"format": "uri"})


class CatalogList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CatalogItemPublic]


class MediaAssetStaff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    catalog_item_id: str
    storage_key: str
    playback_url: str
    hls_url: str | None = None
    mime: str
    measured_duration_ms: int | None = Field(default=None, ge=1)
    source_sha256: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    hls_bundle_sha256: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")


class CatalogItemStaff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: Literal["video", "audio"]
    visual_support: Literal["high", "medium", "low"]
    title_internal: str
    has_l1_translation: Literal[False]
    status: Literal["draft", "level_qa", "published", "archived"]
    revision: int = 1
    qa_round: int = 0


class CatalogItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int
    topic_id: str | None = Field(default=None, min_length=1)
    ci_level: int | None = Field(default=None, ge=0, le=4)
    duration_seconds: int | None = Field(default=None, ge=1)
    media_type: Literal["video", "audio"] | None = None
    visual_support: Literal["high", "medium", "low"] | None = None
    title_internal: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("topic_id", "title_internal", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_patch(self):
        fields = self.model_fields_set - {"revision"}
        if not fields or any(getattr(self, name) is None for name in fields):
            raise ValueError("Provide at least one non-null metadata field")
        return self


class CatalogStaffList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CatalogItemStaff]


class SessionStartBody(BaseModel):
    device_class: Literal["web", "phone", "ipad"]



class LearningSessionPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    device_class: Literal["web", "phone", "ipad"]
    started_at: str = Field(json_schema_extra={"format": "date-time"})
    ended_at: str | None = Field(default=None, json_schema_extra={"format": "date-time"})
    duration_seconds: int | None = None


class LearnerProgressPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minutes_comprehensible: int = Field(ge=0)
    current_ci_level: int = Field(ge=0, le=4)


class SeriesCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    ci_level: str = Field(min_length=1, max_length=10)
    topic_id: str


class SeriesPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    ci_level: str | None = Field(default=None, min_length=1, max_length=10)
    topic_id: str | None = None


class SeriesItemsUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    item_ids: list[str]


class SeriesActionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class SeriesReturnToDraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    reason: str = Field(default="", max_length=500)


class SeriesItemStaffPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_item_id: str = Field(json_schema_extra={"format": "uuid"})
    position: int = Field(ge=1)


class SeriesStaffPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    title: str
    description: str
    ci_level: str
    topic_id: str
    status: Literal["draft", "level_qa", "published", "unpublished"]
    revision: int = Field(ge=1)
    items: list[SeriesItemStaffPublic]
    created_at: str = Field(json_schema_extra={"format": "date-time"})
    updated_at: str = Field(json_schema_extra={"format": "date-time"})


class SeriesStaffSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    title: str
    description: str
    ci_level: str
    topic_id: str
    status: Literal["draft", "level_qa", "published", "unpublished"]
    revision: int = Field(ge=1)
    item_count: int = Field(ge=0)
    created_at: str = Field(json_schema_extra={"format": "date-time"})
    updated_at: str = Field(json_schema_extra={"format": "date-time"})


class SeriesLearnerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    title: str
    description: str
    ci_level: str
    topic_id: str
    available_item_count: int = Field(ge=1)


class SeriesLearnerClipPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_item_id: str = Field(json_schema_extra={"format": "uuid"})
    position: int = Field(ge=1)
    topic_id: str
    ci_level: str
    duration_seconds: int


class SeriesLearnerPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    title: str
    description: str
    ci_level: str
    topic_id: str
    items: list[SeriesLearnerClipPublic]


class SavedScenePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    scene_id: str = Field(json_schema_extra={"format": "uuid"})
    saved_at: datetime


class SavedSceneItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    scene_id: str = Field(json_schema_extra={"format": "uuid"})
    saved_at: datetime
    availability: Literal["available", "stale_version", "unavailable"]
    unavailable_reason: str | None = None
    catalog_item_id: str | None = Field(default=None, json_schema_extra={"format": "uuid"})
    content_version_id: str | None = None
    scene_index: int | None = None
    start_time_seconds: int | None = None
    end_time_seconds: int | None = None
    title_jp: str | None = None
    transcript_jp: str | None = None


class CreateCollectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)


class PatchCollectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)


class UpdateCollectionScenesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    scene_ids: list[str] = Field(max_length=200)


class CollectionPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    name: str
    revision: int = Field(ge=1)
    scene_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class CollectionSceneItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position: int = Field(ge=0)
    scene_id: str = Field(json_schema_extra={"format": "uuid"})
    availability: Literal["available", "stale_version", "unavailable"]
    unavailable_reason: str | None = None
    catalog_item_id: str | None = Field(default=None, json_schema_extra={"format": "uuid"})
    content_version_id: str | None = None
    scene_index: int | None = None
    start_time_seconds: int | None = None
    end_time_seconds: int | None = None
    title_jp: str | None = None
    transcript_jp: str | None = None
    added_at: datetime


class CollectionDetailPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(json_schema_extra={"format": "uuid"})
    name: str
    revision: int = Field(ge=1)
    scene_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    scenes: list[CollectionSceneItemPublic]


class CreateContentReportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_version_id: str
    category: Literal["audio_quality", "scene_timing", "visual_mismatch", "too_difficult", "other"]
    description: str = Field(min_length=1, max_length=1000)
    scene_id: str | None = None
    position_ms: int = Field(default=0, ge=0)


class ContentReportLearnerPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    catalog_item_id: str
    content_version_id: str
    scene_id: str | None = None
    position_ms: int
    category: Literal["audio_quality", "scene_timing", "visual_mismatch", "too_difficult", "other"]
    description: str
    status: Literal["open", "in_review", "resolved", "dismissed"]
    public_reply: str | None = None
    resolution_version_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ContentReportAuditPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    report_id: str
    actor_id: str
    from_status: str | None = None
    to_status: str
    revision: int
    reason: str | None = None
    created_at: datetime


class ContentReportStaffPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    user_id: str
    catalog_item_id: str
    content_version_id: str
    scene_id: str | None = None
    position_ms: int
    category: Literal["audio_quality", "scene_timing", "visual_mismatch", "too_difficult", "other"]
    description: str
    status: Literal["open", "in_review", "resolved", "dismissed"]
    revision: int
    assignee_id: str | None = None
    public_reply: str | None = None
    internal_note: str | None = None
    resolution_version_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ContentReportStaffDetailPublic(ContentReportStaffPublic):
    model_config = ConfigDict(extra="forbid")
    audit_logs: list[ContentReportAuditPublic] = Field(default_factory=list)


class PatchStaffContentReportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    status: Literal["open", "in_review", "resolved", "dismissed"] | None = None
    assignee_id: str | None = None
    public_reply: str | None = None
    internal_note: str | None = None
    resolution_version_id: str | None = None
    reason: str | None = None


class ResumeItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_item_id: str
    playback_id: str | None = None
    position_ms: int
    duration_ms: int
    scene_id: str | None = None
    updated_at: datetime


class ResumeListPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ResumeItemPublic]
    total: int
    limit: int
    offset: int


class StartPlaybackBody(BaseModel):
    content_version_id: str | None = None
    model_config = ConfigDict(extra="forbid")
    catalog_item_id: str
    device_id: str = Field(min_length=1)
    device_info: dict[str, Any] | None = None
    take_over: bool = False


class PlaybackCreatedPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    playback_id: str
    catalog_item_id: str
    epoch: int
    lease_expires_at: datetime
    initial_position_ms: int
    resume_checkpoint: ResumeItemPublic | None = None


class PlaybackStatusPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    playback_id: str
    catalog_item_id: str
    device_id: str
    status: Literal["active", "superseded", "completed", "abandoned"]
    epoch: int
    lease_expires_at: datetime | None = None
    last_seq: int
    last_position_ms: int
    duration_ms: int
    cumulative_active_ms: int
    server_acknowledged_active_ms: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class CheckpointBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    playback_rate: float = Field(ge=0.5, le=2.0, default=1.0)
    state: Literal["playing", "paused", "buffering", "ended"]
    client_cumulative_active_ms: int = Field(ge=0)
    client_epoch: int = Field(ge=1)
    scene_id: str | None = None


class CheckpointAckPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seq: int
    accepted_delta_ms: int
    server_acknowledged_active_ms: int
    lease_expires_at: datetime
    epoch: int


class EndPlaybackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    final_seq: int | None = None
    final_position_ms: int | None = None
    final_duration_ms: int | None = None
    final_playback_rate: float = 1.0
    final_client_cumulative_active_ms: int | None = None
    final_client_epoch: int | None = None
    final_scene_id: str | None = None


class LearningPolicyPublic(BaseModel):
    daily_goal_minutes: int
    timezone: str
    effective_at: datetime


class LearningPreferencesPublic(BaseModel):
    current_policy: LearningPolicyPublic | None = None
    pending_policy: LearningPolicyPublic | None = None
    model_config = ConfigDict(extra="forbid")
    daily_goal_minutes: int
    preferred_topic_ids: list[str]
    timezone: str
    revision: int
    effective_at: datetime
    created_at: datetime
    updated_at: datetime


class UpdateLearningPreferencesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int
    daily_goal_minutes: int | None = Field(default=None, ge=0, le=120)
    preferred_topic_ids: list[str] | None = None
    timezone: str | None = None


class DailyActivityItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str
    timezone: str
    policy_revision: int = Field(ge=1)
    active_ms: int
    active_watch_seconds: int
    goal_minutes: int
    goal_seconds: int
    goal_met: bool
    updated_at: datetime


class LearnerActivityResponsePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[DailyActivityItemPublic]
    total_active_watch_seconds: int
    days_goal_met: int
    current_streak_days: int
    longest_streak_days: int


class WatchHistoryItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    playback_id: str
    catalog_item_id: str
    title_jp: str | None = None
    item_type: str
    topic_id: str
    duration_seconds: int
    status: str
    last_position_ms: int
    total_active_ms: int
    content_version_id: str
    created_at: datetime
    updated_at: datetime


class WatchHistoryResponsePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[WatchHistoryItemPublic]
    next_cursor: str | None = None


class HistoryDeletionCreatedPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deletion_id: str
    cutoff_time: datetime
    status: Literal["queued", "running", "completed", "failed"]
    message: str


class HistoryDeletionStatusPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deletion_id: str
    user_id: str
    cutoff_time: datetime
    status: Literal["queued", "running", "completed", "failed"]
    records_deleted: int
    attempts: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class RecommendedItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_item_id: str
    media_type: str
    topic_id: str
    duration_seconds: int
    ci_level: int
    reason: Literal["continue_series", "preferred_topic", "same_level", "editor_pick"]
    title_jp: str | None = None
    series_id: str | None = None
    series_title: str | None = None


class RecommendationsResponsePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RecommendedItemPublic]
    strategy_version: str


class TranscriptSegmentPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: str
    text_ja: str = Field(..., max_length=500)


class TranscriptRevisionPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    catalog_item_id: str
    content_version_id: str
    revision: int
    status: Literal["draft", "qa_submitted", "approved", "returned_to_draft"]
    segments: list[TranscriptSegmentPublic]
    provenance: Literal["manual_teacher", "ai_assisted", "imported"]
    created_by: str
    approved_by: str | None = None
    return_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SaveTranscriptDraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_version_id: str
    expected_revision: int
    segments: list[TranscriptSegmentPublic]
    provenance: Literal["manual_teacher", "ai_assisted", "imported"] = "manual_teacher"


class SubmitTranscriptQABody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_version_id: str
    expected_revision: int


class ApproveTranscriptBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_version_id: str
    expected_revision: int


class ReturnTranscriptToDraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_version_id: str
    expected_revision: int
    reason: str = Field(..., min_length=1, max_length=1000)


class CreateLanguageAnalysisJobBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transcript_revision_id: str


class TokenSpanPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surface: str
    char_type: str
    start_offset: int
    end_offset: int
    reading_hint: str | None = None
    lemma: str | None = None


class LanguageAnalysisJobPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    catalog_item_id: str
    transcript_revision_id: str
    status: Literal["queued", "running", "completed", "failed"]
    results: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class HighlightSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_offset: int
    end_offset: int


class SearchResultItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_item_id: str
    content_version_id: str
    scene_id: str
    scene_index: int
    start_time_seconds: int
    end_time_seconds: int
    matched_text_ja: str
    highlight_spans: list[HighlightSpan]
    match_kind: Literal["exact_phrase", "token_match"]
    ci_level: int
    topic_id: str
    title_jp: str


class SearchResponsePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[SearchResultItemPublic]
    next_cursor: str | None = None
    total_estimated: int | None = None


class AiUsageItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    account_id: str
    job_id: str
    kind: str
    status: str
    provider: str
    provider_request_id: str | None = None
    attempt: int
    audio_seconds: int
    input_tokens: int
    output_tokens: int
    cost_micros: int
    currency: str
    policy_version: str
    created_at: datetime
    settled_at: datetime | None = None
    description: str | None = None


class AiUsageListResponsePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AiUsageItemPublic]
    total_count: int
    from_date: datetime
    to_date: datetime


class AiUsageSummaryItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    currency: str
    date: str
    total_audio_seconds: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_micros: int
    events_count: int


class AiUsageSummaryResponsePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_date: datetime
    to_date: datetime
    summary: list[AiUsageSummaryItemPublic]
    total_audio_seconds: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_micros: int


class CreateContentJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_version_id: str
    task: Literal["transcript", "segmentation"]
    language: str = "ja"
    estimated_audio_seconds: int = Field(
        default=300,
        ge=0,
        le=86400,
        deprecated=True,
        description="Compatibility hint only; quota is estimated from server-observed media duration.",
    )
    estimated_cost_micros: int = Field(
        default=500000,
        ge=0,
        le=1000000000,
        deprecated=True,
        description="Compatibility hint only; quota uses the versioned server pricing policy.",
    )


class ApplyContentJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int
    segments: list[dict[str, str]] | None = None


class ContentJobResponsePublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    catalog_item_id: str
    content_version_id: str
    task: str
    language: str
    status: str
    progress: float
    provenance: dict[str, Any]
    result_draft: dict[str, Any] | None = None
    error_message: str | None = None
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CatalogReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    notes: str = Field(default="", max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def trim_notes(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_needs_notes(self):
        if self.decision == "reject" and not self.notes:
            raise ValueError("Rejection requires notes")
        return self


class CatalogReviewPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    qa_round: int
    decision: Literal["approve", "reject"]
    notes: str
    reviewed_by: str
    reviewed_at: str = Field(json_schema_extra={"format": "date-time"})


class CatalogItemDetail(CatalogItemStaff):
    qa_round: int
    media: list[MediaAssetStaff]
    reviews: list[CatalogReviewPublic]
