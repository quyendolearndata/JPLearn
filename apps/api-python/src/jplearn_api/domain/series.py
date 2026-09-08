"""Series aggregate root and invariants (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from jplearn_api.domain.errors import InvalidDomainStateError, RevisionConflictError


@dataclass(frozen=True)
class SeriesItem:
    """An ordered item reference within a Series."""

    catalog_item_id: str
    position: int

    def __post_init__(self) -> None:
        if not self.catalog_item_id:
            raise InvalidDomainStateError("catalog_item_id must not be empty")
        if self.position < 1:
            raise InvalidDomainStateError("position must be >= 1")


@dataclass
class Series:
    """Series aggregate root managing episodes/items order and publishing workflow."""

    id: str
    title: str
    description: str
    ci_level: str
    topic_id: str
    status: str = "draft"
    revision: int = 1
    items: list[SeriesItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def update_metadata(
        self,
        expected_revision: int,
        title: str | None = None,
        description: str | None = None,
        ci_level: str | None = None,
        topic_id: str | None = None,
    ) -> None:
        if self.revision != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, but current revision is {self.revision}"
            )
        if self.status not in ("draft", "level_qa"):
            raise InvalidDomainStateError(f"Cannot update metadata when status is '{self.status}'")

        if title is not None:
            clean_title = title.strip()
            if not clean_title:
                raise InvalidDomainStateError("Series title must not be empty")
            self.title = clean_title
        if description is not None:
            self.description = description.strip()
        if ci_level is not None:
            self.ci_level = str(ci_level)
        if topic_id is not None:
            self.topic_id = topic_id

        self.revision += 1
        self.updated_at = datetime.now(UTC)

    def update_items(self, expected_revision: int, catalog_item_ids: list[str]) -> None:
        if self.revision != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, but current revision is {self.revision}"
            )
        if self.status not in ("draft", "level_qa"):
            raise InvalidDomainStateError(f"Cannot update items when status is '{self.status}'")

        if len(catalog_item_ids) != len(set(catalog_item_ids)):
            raise InvalidDomainStateError("Duplicate catalog item ids in series")

        self.items = [SeriesItem(catalog_item_id=cid, position=idx + 1) for idx, cid in enumerate(catalog_item_ids)]
        self.revision += 1
        self.updated_at = datetime.now(UTC)

    def submit_qa(self, expected_revision: int) -> None:
        if self.revision != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, but current revision is {self.revision}"
            )
        if self.status != "draft":
            raise InvalidDomainStateError("Only draft series can be submitted for QA")
        if not self.items:
            raise InvalidDomainStateError("Series must have at least one item to submit for QA")

        self.status = "level_qa"
        self.revision += 1
        self.updated_at = datetime.now(UTC)

    def return_to_draft(self, expected_revision: int, reason: str = "") -> None:
        if self.revision != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, but current revision is {self.revision}"
            )
        if self.status != "level_qa":
            raise InvalidDomainStateError("Only series in level_qa can be returned to draft")

        self.status = "draft"
        self.revision += 1
        self.updated_at = datetime.now(UTC)

    def publish(self, expected_revision: int, published_catalog_ids: set[str]) -> None:
        if self.revision != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, but current revision is {self.revision}"
            )
        if self.status != "level_qa":
            raise InvalidDomainStateError("Only series in level_qa can be published")
        if not self.items:
            raise InvalidDomainStateError("Series must have at least one item to publish")

        unpub = [it.catalog_item_id for it in self.items if it.catalog_item_id not in published_catalog_ids]
        if unpub:
            raise InvalidDomainStateError(f"Cannot publish series: constituent clips {unpub} are not published")

        self.status = "published"
        self.revision += 1
        self.updated_at = datetime.now(UTC)

    def unpublish(self, expected_revision: int) -> None:
        if self.revision != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, but current revision is {self.revision}"
            )
        if self.status != "published":
            raise InvalidDomainStateError("Only published series can be unpublished")

        self.status = "unpublished"
        self.revision += 1
        self.updated_at = datetime.now(UTC)
