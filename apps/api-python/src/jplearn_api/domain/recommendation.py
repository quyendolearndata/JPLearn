"""Domain entities, enums, and projections for content recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecommendationReason(str, Enum):
    """Reason code explaining why an item was recommended."""

    CONTINUE_SERIES = "continue_series"
    PREFERRED_TOPIC = "preferred_topic"
    SAME_LEVEL = "same_level"
    EDITOR_PICK = "editor_pick"


@dataclass(frozen=True)
class RecommendedItemProjection:
    """Projection of an item recommended to a learner."""

    catalog_item_id: str
    media_type: str
    topic_id: str
    duration_seconds: int
    ci_level: int
    reason: RecommendationReason
    title_jp: str | None = None
    series_id: str | None = None
    series_title: str | None = None
