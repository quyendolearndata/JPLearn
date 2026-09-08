"""Catalog domain aggregate root and invariants (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field

from jplearn_api.domain.errors import InvalidDomainStateError, MediaInvariantError


@dataclass(frozen=True)
class MediaRef:
    """Lightweight media asset reference owned by CatalogItem aggregate."""

    id: str
    storage_key: str
    playback_url: str | None = None
    hls_url: str | None = None
    mime: str = "video/mp4"
    measured_duration_ms: int | None = None
    source_sha256: str | None = None
    hls_bundle_sha256: str | None = None


@dataclass
class CatalogItem:
    """Catalog item aggregate root managing state machine and publication invariants."""

    id: str
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    visual_support: str
    title_internal: str
    created_by: str
    revision: int = 1
    has_l1_translation: bool = False
    spoken_language: str = "ja"
    status: str = "draft"
    media: list[MediaRef] = field(default_factory=list)

    def submit_for_qa(self) -> None:
        """Transition draft item to level_qa."""
        if self.status != "draft":
            raise InvalidDomainStateError("Only draft items can be submitted for QA")
        self.status = "level_qa"
        self.revision += 1

    def publish(self) -> None:
        """Transition level_qa item to published after asserting publication invariants."""
        if self.status != "level_qa":
            raise InvalidDomainStateError("Only level_qa items can be published")
        if not self.media:
            raise MediaInvariantError("Cannot publish without media: upload a playback source first (FR-CAT-002)")
        if self.has_l1_translation:
            raise InvalidDomainStateError("Cannot publish item with L1 translation (FR-CAT-002)")
        self.status = "published"
        self.revision += 1

    def unpublish(self) -> None:
        """Transition published item back to draft."""
        if self.status != "published":
            raise InvalidDomainStateError("Only published items can be unpublished")
        self.status = "draft"
        self.revision += 1

    def return_to_draft(self) -> None:
        """Transition level_qa item back to draft."""
        if self.status != "level_qa":
            raise InvalidDomainStateError("Only level_qa items can be returned to draft")
        self.status = "draft"
        self.revision += 1

    def update_draft_metadata(
        self,
        *,
        topic_id: str | None = None,
        ci_level: int | None = None,
        duration_seconds: int | None = None,
        media_type: str | None = None,
        visual_support: str | None = None,
        title_internal: str | None = None,
    ) -> None:
        """Update draft item metadata and increment revision."""
        if self.status != "draft":
            raise InvalidDomainStateError("Only draft items can be modified")
        if topic_id is not None:
            self.topic_id = topic_id
        if ci_level is not None:
            self.ci_level = ci_level
        if duration_seconds is not None:
            self.duration_seconds = duration_seconds
        if media_type is not None:
            self.media_type = media_type
        if visual_support is not None:
            self.visual_support = visual_support
        if title_internal is not None:
            self.title_internal = title_internal
        self.revision += 1

    def archive(self) -> None:
        """Mark catalog item as archived."""
        self.status = "archived"
