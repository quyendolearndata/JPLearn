"""Learning sessions and learner progress domain entities (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from jplearn_api.domain.errors import (
    EntityNotFoundError,
    ForbiddenError,
    SessionAlreadyEndedError,
)

ZOMBIE_SESSION_SECONDS = 4 * 60 * 60  # 4 hours


def minutes_from_duration(duration_seconds: int) -> int:
    """Pure domain calculation for comprehensible minutes.

    - Negative durations count 0 minutes.
    - Durations less than 60 seconds count 0 minutes.
    - Durations strictly over 4 hours (zombie sessions) count 0 minutes.
    - Otherwise returns integer whole minutes (floor division by 60).
    """
    if duration_seconds < 0 or duration_seconds > ZOMBIE_SESSION_SECONDS:
        return 0
    return duration_seconds // 60


@dataclass
class LearningSession:
    """Learning session entity tracking session duration and lifecycle."""

    id: str
    user_id: str
    device_class: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None

    def end(self, ended_at: datetime) -> int:
        """End session exactly-once and return duration in seconds."""
        if self.ended_at is not None:
            raise SessionAlreadyEndedError("Session already ended")
        self.ended_at = ended_at
        duration = int((ended_at - self.started_at).total_seconds())
        self.duration_seconds = duration
        return duration


@dataclass
class LearnerProgress:
    """Learner progress aggregate tracking comprehensible minutes and CI level."""

    user_id: str
    minutes_comprehensible: int = 0
    current_ci_level: int = 0
    updated_at: datetime | None = None

    def add_minutes(self, minutes: int, now: datetime) -> None:
        """Add verified comprehensible minutes."""
        self.minutes_comprehensible += minutes
        self.updated_at = now


# Domain aliases for legacy characterization test compatibility
SessionNotFound = EntityNotFoundError
ForbiddenSession = ForbiddenError
SessionAlreadyEnded = SessionAlreadyEndedError
LearnerProgressNotFound = EntityNotFoundError
