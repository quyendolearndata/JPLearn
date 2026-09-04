from __future__ import annotations

# Pure domain policy for learning sessions (FR-SES-002, FR-PRG-001)

ZOMBIE_SESSION_SECONDS = 4 * 60 * 60  # 4 hours


class SessionNotFound(Exception):
    pass


class ForbiddenSession(Exception):
    pass


class SessionAlreadyEnded(Exception):
    pass


class LearnerProgressNotFound(Exception):
    pass


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
