"""Personal collections domain entities (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from jplearn_api.domain.saved_scene import SceneAvailability


@dataclass
class PersonalCollection:
    """A user-created private collection of bookmarked scenes."""

    id: str
    user_id: str
    name: str
    revision: int
    created_at: datetime
    updated_at: datetime
    scene_count: int = 0


@dataclass
class CollectionSceneDetail:
    """Detailed view of a scene within a personal collection."""

    position: int
    scene_id: str
    availability: SceneAvailability
    scene: dict | None
    reason: str | None
    added_at: datetime


@dataclass
class CollectionDetail:
    """Full detail view of a collection including ordered scenes and availability."""

    id: str
    user_id: str
    name: str
    revision: int
    scene_count: int
    created_at: datetime
    updated_at: datetime
    scenes: list[CollectionSceneDetail] = field(default_factory=list)
