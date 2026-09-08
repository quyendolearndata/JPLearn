"""Playback tracking, heartbeat accounting, and resume domain entities (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

LEASE_DURATION_SECONDS = 45
HEARTBEAT_GAP_THRESHOLD_SECONDS = 30
MIN_PLAYBACK_RATE = 0.5
MAX_PLAYBACK_RATE = 2.0
CLOCK_SKEW_TOLERANCE_MS = 2000
DEFAULT_DAILY_GOAL_MINUTES = 15
DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"


class PlaybackStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"
    ABANDONED = "abandoned"


class PlayerState(StrEnum):
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"
    ENDED = "ended"


@dataclass
class LearnerPlaybackState:
    """Represents a learner's active single-playback lease and concurrency epoch."""

    user_id: str
    active_playback_id: str | None
    current_epoch: int
    lease_expires_at: datetime
    device_class: str
    client_instance_id: str
    updated_at: datetime

    def is_lease_active(self, now: datetime) -> bool:
        # compare unaware or aware datetime
        now_cmp = now.replace(tzinfo=None) if self.lease_expires_at.tzinfo is None else now
        return bool(self.active_playback_id and self.lease_expires_at > now_cmp)

    def bump_epoch(self) -> None:
        self.current_epoch += 1


@dataclass
class PlaybackSession:
    """An individual playback session for an item version on a specific device."""

    id: str
    user_id: str
    catalog_item_id: str
    content_version_id: str
    epoch: int
    device_class: str
    client_instance_id: str
    status: PlaybackStatus
    last_seq: int
    total_active_ms: int
    last_position_ms: int
    last_server_time: datetime
    last_client_cumulative_ms: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


@dataclass
class PlaybackReceipt:
    """An idempotent receipt capturing an accepted checkpoint or end event."""

    playback_id: str
    seq: int
    request_hash: str
    accepted_delta_ms: int
    cumulative_active_ms: int
    response_payload: dict[str, Any]
    created_at: datetime


@dataclass
class PlaybackCheckpoint:
    """Last known playback position for cross-device resume."""

    user_id: str
    catalog_item_id: str
    content_version_id: str
    position_ms: int
    updated_at: datetime


@dataclass
class LearningPreferences:
    """Learner time accounting preferences (daily goal, IANA timezone, preferred topics)."""

    user_id: str
    daily_goal_minutes: int
    timezone: str
    revision: int
    effective_at: datetime
    created_at: datetime
    updated_at: datetime
    preferred_topic_ids: list[str] = field(default_factory=list)


@dataclass
class LearnerDailyActivity:
    """Aggregated active immersion time for a specific calendar date in user's timezone."""

    user_id: str
    date: str  # YYYY-MM-DD
    timezone: str
    active_ms: int
    goal_minutes: int
    goal_met: bool
    updated_at: datetime
    policy_revision: int = 1


class DeletionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class HistoryDeletionJob:
    """A durable deletion job managing watch history purging before a cutoff time."""

    id: str
    user_id: str
    status: DeletionStatus
    cutoff_time: datetime
    records_deleted: int
    attempts: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


@dataclass
class WatchHistoryItemProjection:
    """Projection of playback item in learner's watch history."""

    playback_id: str
    catalog_item_id: str
    title_jp: str | None
    item_type: str
    topic_id: str
    duration_seconds: int
    status: str
    last_position_ms: int
    total_active_ms: int
    content_version_id: str
    created_at: datetime
    updated_at: datetime
