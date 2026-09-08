"""Saved scenes domain entities (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SceneAvailability(str, Enum):
    AVAILABLE = "available"
    STALE_VERSION = "stale_version"
    UNAVAILABLE = "unavailable"


@dataclass
class SavedScene:
    """A bookmarked scene reference owned by a learner."""

    id: str
    user_id: str
    scene_id: str
    saved_at: datetime
