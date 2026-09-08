"""Durable provider attempts and operator decisions, independent of job leases."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class AiAttempt:
    id: str
    job_id: str
    attempt_number: int
    provider: str
    idempotency_key: str
    state: str
    lease_expires_at: datetime
    created_at: datetime
    updated_at: datetime
    provider_request_id: str | None = None
    usage: dict[str, Any] | None = None
    evidence: str | None = None
    resolved_by: str | None = None
    resolution_hash: str | None = None
