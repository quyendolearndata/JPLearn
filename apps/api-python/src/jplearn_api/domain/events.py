"""Domain events (Pure Python dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionStarted:
    user_id: str
    session_id: str
    created_at: datetime


@dataclass(frozen=True)
class SessionEnded:
    user_id: str
    session_id: str
    ended_at: datetime


@dataclass(frozen=True)
class MinutesComprehensibleAdded:
    user_id: str
    session_id: str
    minutes: int
    created_at: datetime


@dataclass(frozen=True)
class LevelExposed:
    user_id: str
    session_id: str
    ci_level: int
    created_at: datetime
