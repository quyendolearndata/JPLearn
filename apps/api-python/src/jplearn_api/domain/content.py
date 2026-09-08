"""Content versions and scene breakdown domain entities (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from jplearn_api.domain.errors import ConflictError, InvalidDomainStateError


@dataclass(frozen=True)
class Scene:
    """A scene segment within a content version with timestamp and Japanese transcript."""

    id: str
    scene_index: int
    start_time_seconds: int
    end_time_seconds: int
    title_jp: str
    transcript_jp: str

    def __post_init__(self) -> None:
        if self.start_time_seconds < 0:
            raise InvalidDomainStateError("start_time_seconds must be >= 0")
        if self.end_time_seconds <= self.start_time_seconds:
            raise InvalidDomainStateError("end_time_seconds must be greater than start_time_seconds")
        if not self.title_jp or not self.title_jp.strip():
            raise InvalidDomainStateError("title_jp cannot be empty")
        if not self.transcript_jp or not self.transcript_jp.strip():
            raise InvalidDomainStateError("transcript_jp cannot be empty")


@dataclass
class ContentVersion:
    """Content version aggregate representing an immutable or draft set of scenes for a catalog item."""

    id: str
    catalog_item_id: str
    version_number: int = 1
    revision: int = 1
    is_frozen: bool = False
    is_published: bool = False
    created_at: datetime | None = None
    published_at: datetime | None = None
    scenes: list[Scene] = field(default_factory=list)

    media_asset_id: str | None = None
    media_storage_key: str | None = None
    media_hls_url: str | None = None
    duration_seconds: int | None = None
    duration_source: str = "legacy_metadata"
    source_sha256: str | None = None
    measured_duration_ms: int | None = None
    hls_bundle_sha256: str | None = None

    def pin_source(
        self,
        asset_id: str,
        storage_key: str,
        hls_url: str | None,
        duration_seconds: int,
        hls_bundle_sha256: str | None = None,
    ) -> None:
        if self.is_frozen or self.is_published:
            raise InvalidDomainStateError("Cannot change a frozen content source")
        if duration_seconds <= 0 or any(s.end_time_seconds > duration_seconds for s in self.scenes):
            raise InvalidDomainStateError("Scenes exceed content duration")
        self.media_asset_id = asset_id
        self.media_storage_key = storage_key
        self.media_hls_url = hls_url
        self.duration_seconds = duration_seconds
        self.hls_bundle_sha256 = hls_bundle_sha256
        # Snapshot provenance is explicit; metadata is not a media probe.
        self.duration_source = "catalog_metadata"

    def assert_source(
        self,
        asset_id: str,
        storage_key: str,
        hls_url: str | None,
        duration_seconds: int,
        hls_bundle_sha256: str | None = None,
    ) -> None:
        if not self.is_frozen or (
            self.media_asset_id, self.media_storage_key, self.media_hls_url, self.duration_seconds
        ) != (asset_id, storage_key, hls_url, duration_seconds) or self.hls_bundle_sha256 != hls_bundle_sha256:
            raise ConflictError("Content source changed since QA; return to draft and submit again")

    def freeze_for_qa(self) -> None:
        """Freeze draft content version when submitted for Level QA."""
        if self.is_published:
            raise InvalidDomainStateError("Published content version cannot be frozen for QA")
        self.is_frozen = True

    def unfreeze_return_to_draft(self) -> None:
        """Unfreeze content version when returned to draft."""
        if self.is_published:
            raise InvalidDomainStateError("Published content version cannot be returned to draft")
        self.is_frozen = False

    def publish(self, published_at: datetime) -> None:
        """Mark content version as published."""
        self.is_published = True
        self.is_frozen = True
        self.published_at = published_at

    def update_scenes(
        self,
        new_scenes: list[Scene],
        expected_revision: int,
        max_duration: int | None = None,
    ) -> None:
        """Update scenes of draft content version under optimistic CAS locking."""
        if self.is_frozen or self.is_published:
            raise InvalidDomainStateError("Cannot modify frozen or published content version")
        if self.revision != expected_revision:
            raise ConflictError(
                f"Revision mismatch: expected {expected_revision}, current {self.revision}"
            )

        sorted_scenes = sorted(new_scenes, key=lambda s: s.scene_index)
        for i, sc in enumerate(sorted_scenes):
            if sc.scene_index != i + 1:
                raise InvalidDomainStateError(
                    f"Scene indices must be contiguous starting from 1 (got {sc.scene_index} at position {i+1})"
                )
            if max_duration is not None and sc.end_time_seconds > max_duration:
                raise InvalidDomainStateError(
                    f"Scene end time ({sc.end_time_seconds}s) exceeds clip duration ({max_duration}s)"
                )
            if i > 0:
                prev = sorted_scenes[i - 1]
                if sc.start_time_seconds < prev.end_time_seconds:
                    raise InvalidDomainStateError("Scenes must not overlap and must be ordered chronologically")

        self.scenes = sorted_scenes
        self.revision += 1
