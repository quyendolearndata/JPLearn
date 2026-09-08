from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class UserDTO:
    id: str
    email: str
    roles: list[str]


@dataclass(frozen=True)
class AuthSessionDTO:
    access_token: str
    user: UserDTO


@dataclass(frozen=True)
class CatalogItemStaffDTO:
    id: str
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    visual_support: str
    title_internal: str
    has_l1_translation: bool
    status: str
    revision: int = 1
    qa_round: int = 0


@dataclass(frozen=True)
class CatalogItemPublicDTO:
    id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    topic_id: str
    visual_support: str
    playback_url: str | None
    hls_url: str | None


@dataclass(frozen=True)
class LearningSessionDTO:
    id: str
    device_class: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None


@dataclass(frozen=True)
class LearnerProgressDTO:
    minutes_comprehensible: int
    current_ci_level: int


@dataclass(frozen=True)
class MediaAssetStaffDTO:
    id: str
    catalog_item_id: str
    storage_key: str
    playback_url: str
    hls_url: str | None
    mime: str
    measured_duration_ms: int | None = None
    source_sha256: str | None = None
    hls_bundle_sha256: str | None = None


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int
    length: int
    total_size: int


@dataclass(frozen=True)
class MediaStreamDTO:
    content_stream: AsyncIterator[bytes]
    content_type: str
    total_size: int
    range: ByteRange | None = None


@dataclass(frozen=True)
class SceneDTO:
    id: str
    scene_index: int
    start_time_seconds: int
    end_time_seconds: int
    title_jp: str
    transcript_jp: str


@dataclass(frozen=True)
class ContentVersionDTO:
    id: str
    catalog_item_id: str
    version_number: int
    revision: int
    is_frozen: bool
    is_published: bool
    scenes: list[SceneDTO]
    created_at: datetime | None = None
    published_at: datetime | None = None


@dataclass(frozen=True)
class SearchResultItemDTO:
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


@dataclass(frozen=True)
class SearchResponseDTO:
    items: list[SearchResultItemDTO]
    next_cursor: str | None = None
    total_estimated: int | None = None


@dataclass(frozen=True)
class AiUsageItemDTO:
    id: str
    account_id: str
    job_id: str
    kind: str
    status: str
    provider: str
    provider_request_id: str | None
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


@dataclass(frozen=True)
class AiUsageListDTO:
    items: list[AiUsageItemDTO]
    total_count: int
    from_date: datetime
    to_date: datetime


@dataclass(frozen=True)
class AiUsageSummaryItemDTO:
    provider: str
    currency: str
    date: str
    total_audio_seconds: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_micros: int
    events_count: int


@dataclass(frozen=True)
class AiUsageSummaryDTO:
    from_date: datetime
    to_date: datetime
    summary: list[AiUsageSummaryItemDTO]
    total_audio_seconds: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_micros: int


@dataclass(frozen=True)
class ContentJobDTO:
    id: str
    catalog_item_id: str
    content_version_id: str
    task: str
    language: str
    status: str
    progress: float
    provenance: dict[str, Any]
    result_draft: dict[str, Any] | None
    error_message: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
