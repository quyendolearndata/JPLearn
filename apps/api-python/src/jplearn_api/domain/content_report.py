"""Content report domain entities (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReportCategory(StrEnum):
    AUDIO_QUALITY = "audio_quality"
    SCENE_TIMING = "scene_timing"
    VISUAL_MISMATCH = "visual_mismatch"
    TOO_DIFFICULT = "too_difficult"
    OTHER = "other"


class ReportStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass
class ContentReport:
    """A user-submitted issue report regarding a published catalog item scene or timing."""

    id: str
    user_id: str
    catalog_item_id: str
    content_version_id: str
    scene_id: str | None
    position_ms: int
    category: ReportCategory
    description: str
    status: ReportStatus
    public_reply: str | None
    internal_note: str | None
    assignee_id: str | None
    resolution_version_id: str | None
    idempotency_key: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass
class ContentReportAudit:
    """An audit log entry capturing a status/moderation change on a content report."""

    id: str
    report_id: str
    actor_id: str
    from_status: ReportStatus
    to_status: ReportStatus
    revision: int
    reason: str | None
    created_at: datetime
