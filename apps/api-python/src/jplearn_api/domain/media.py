"""Media domain entities and invariants (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from jplearn_api.domain.errors import DomainError


class MediaUploadState(str, Enum):
    """Lifecycle states of media upload process."""

    STAGED = "STAGED"
    PROMOTED = "PROMOTED"
    COMMITTED = "COMMITTED"
    ROLLBACK_CONFIRMED = "ROLLBACK_CONFIRMED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class RangeNotSatisfiableError(DomainError):
    """Raised when an HTTP byte range cannot be satisfied."""

    def __init__(self, total_size: int) -> None:
        super().__init__("Range Not Satisfiable")
        self.total_size = total_size


@dataclass
class MediaAsset:
    """Media asset domain entity."""

    id: str
    catalog_item_id: str
    storage_key: str
    mime: str = "video/mp4"
    playback_url: str | None = None
    hls_url: str | None = None
