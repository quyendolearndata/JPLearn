"""Domain entities and business rules for AI Content Jobs (ADR-007 PR8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from jplearn_api.domain.errors import (
    ConflictError,
    InvalidDomainStateError,
)


class ContentJobTask(str, Enum):
    TRANSCRIPT = "transcript"
    SEGMENTATION = "segmentation"


class ContentJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ContentJob:
    """Represents a durable AI transcription / segmentation job."""

    id: str
    catalog_item_id: str
    content_version_id: str
    task: ContentJobTask
    source_hash: str
    config_hash: str
    idempotency_key: str
    created_by: str
    language: str = "ja"
    status: ContentJobStatus = ContentJobStatus.QUEUED
    progress: float = 0.0
    provenance: dict[str, Any] = field(default_factory=dict)
    attempt: int = 0
    max_attempts: int = 3
    attempt_token: str | None = None
    lease_expires_at: datetime | None = None
    result_draft: dict[str, Any] | None = None
    error_message: str | None = None
    applied_at: datetime | None = None
    applied_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def can_claim(self, now: datetime) -> bool:
        """Check if job is ready to be claimed by a worker."""
        if self.status == ContentJobStatus.QUEUED:
            return self.attempt < self.max_attempts
        # An expired lease does not prove that the provider did not bill us.
        # Keep running attempts for reconciliation instead of resubmitting media.
        return False

    def claim_lease(self, token: str, expires_at: datetime, now: datetime) -> None:
        """Claim job lease by an active worker attempt."""
        if not self.can_claim(now):
            raise InvalidDomainStateError(f"Job {self.id} cannot be claimed in state {self.status}")
        self.status = ContentJobStatus.RUNNING
        self.attempt += 1
        self.attempt_token = token
        self.lease_expires_at = expires_at
        self.updated_at = now

    def record_success(
        self,
        result_draft: dict[str, Any],
        provenance: dict[str, Any],
        now: datetime,
    ) -> None:
        """Transition job to SUCCEEDED and store result draft."""
        if self.status != ContentJobStatus.RUNNING:
            raise InvalidDomainStateError(f"Cannot record success for job in state {self.status}")
        self.status = ContentJobStatus.SUCCEEDED
        self.progress = 1.0
        self.result_draft = result_draft
        self.provenance = provenance
        self.lease_expires_at = None
        self.attempt_token = None
        self.error_message = None
        self.updated_at = now

    def record_failure(
        self,
        error_message: str,
        retryable: bool,
        now: datetime,
    ) -> None:
        """Handle execution failure, scheduling retry or marking permanently FAILED."""
        self.error_message = error_message
        self.lease_expires_at = None
        self.attempt_token = None
        self.updated_at = now

        if retryable and self.attempt < self.max_attempts:
            self.status = ContentJobStatus.QUEUED
        else:
            self.status = ContentJobStatus.FAILED

    def cancel(self, now: datetime) -> None:
        """Cancel the job if not already succeeded or cancelled."""
        if self.status == ContentJobStatus.SUCCEEDED:
            raise ConflictError("Cannot cancel an already succeeded job")
        if self.status == ContentJobStatus.CANCELLED:
            return  # Idempotent cancel
        self.status = ContentJobStatus.CANCELLED
        self.lease_expires_at = None
        self.attempt_token = None
        self.updated_at = now

    def apply(self, applied_by: str, now: datetime) -> None:
        """Mark job results as applied to catalog transcript."""
        if self.status != ContentJobStatus.SUCCEEDED:
            raise InvalidDomainStateError("Can only apply results of a succeeded job")
        if self.applied_at is not None:
            raise ConflictError("Job results have already been applied")
        self.applied_at = now
        self.applied_by = applied_by
        self.updated_at = now
