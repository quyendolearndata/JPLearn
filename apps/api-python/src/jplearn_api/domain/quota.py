"""AI Quota and Usage Ledger Domain Models (Pure Python, ADR-007 PR8c)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

from jplearn_api.domain.errors import (
    InvalidReservationStateError,
    QuotaExceededError,
)


@dataclass
class AiUsageLedgerEntry:
    id: str
    account_id: str
    job_id: str
    user_id: str
    idempotency_key: str
    kind: str  # 'reservation', 'settlement', 'release', 'reconciliation'
    status: str  # 'reserved', 'settled', 'released', 'reconciled'
    provider: str
    provider_request_id: str | None
    attempt: int
    audio_seconds: int
    input_tokens: int
    output_tokens: int
    cost_micros: int
    currency: str
    policy_version: str
    created_at: datetime
    settled_at: datetime | None = None
    description: str | None = None


@dataclass
class QuotaAccount:
    id: str
    user_id: str | None
    name: str
    max_audio_seconds: int
    max_input_tokens: int
    max_output_tokens: int
    max_cost_micros: int
    reserved_audio_seconds: int = 0
    reserved_input_tokens: int = 0
    reserved_output_tokens: int = 0
    reserved_cost_micros: int = 0
    used_audio_seconds: int = 0
    used_input_tokens: int = 0
    used_output_tokens: int = 0
    used_cost_micros: int = 0
    policy_version: str = "v1"
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def available_audio_seconds(self) -> int:
        return max(0, self.max_audio_seconds - (self.reserved_audio_seconds + self.used_audio_seconds))

    @property
    def available_input_tokens(self) -> int:
        return max(0, self.max_input_tokens - (self.reserved_input_tokens + self.used_input_tokens))

    @property
    def available_output_tokens(self) -> int:
        return max(0, self.max_output_tokens - (self.reserved_output_tokens + self.used_output_tokens))

    @property
    def available_cost_micros(self) -> int:
        return max(0, self.max_cost_micros - (self.reserved_cost_micros + self.used_cost_micros))

    def can_reserve(
        self,
        audio_seconds: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_micros: int = 0,
    ) -> bool:
        if not self.is_active:
            return False
        if audio_seconds > 0 and (self.reserved_audio_seconds + self.used_audio_seconds + audio_seconds) > self.max_audio_seconds:
            return False
        if input_tokens > 0 and (self.reserved_input_tokens + self.used_input_tokens + input_tokens) > self.max_input_tokens:
            return False
        if output_tokens > 0 and (self.reserved_output_tokens + self.used_output_tokens + output_tokens) > self.max_output_tokens:
            return False
        if cost_micros > 0 and (self.reserved_cost_micros + self.used_cost_micros + cost_micros) > self.max_cost_micros:
            return False
        return True

    def reserve(
        self,
        job_id: str,
        user_id: str,
        idempotency_key: str,
        provider: str,
        audio_seconds: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_micros: int = 0,
        currency: str = "USD",
        entry_id: str | None = None,
        now: datetime | None = None,
        description: str | None = None,
    ) -> AiUsageLedgerEntry:
        if not self.is_active:
            raise QuotaExceededError("Quota account is inactive")
        if not self.can_reserve(audio_seconds, input_tokens, output_tokens, cost_micros):
            raise QuotaExceededError("Insufficient AI quota for reservation")

        ts = now or datetime.now(timezone.utc)
        self.reserved_audio_seconds += audio_seconds
        self.reserved_input_tokens += input_tokens
        self.reserved_output_tokens += output_tokens
        self.reserved_cost_micros += cost_micros
        self.updated_at = ts

        return AiUsageLedgerEntry(
            id=entry_id or str(uuid.uuid4()),
            account_id=self.id,
            job_id=job_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
            kind="reservation",
            status="reserved",
            provider=provider,
            provider_request_id=None,
            attempt=1,
            audio_seconds=audio_seconds,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_micros=cost_micros,
            currency=currency,
            policy_version=self.policy_version,
            created_at=ts,
            description=description,
        )

    def settle(
        self,
        reservation_entry: AiUsageLedgerEntry,
        actual_audio_seconds: int,
        actual_input_tokens: int,
        actual_output_tokens: int,
        actual_cost_micros: int,
        provider_request_id: str | None = None,
        attempt: int = 1,
        entry_id: str | None = None,
        now: datetime | None = None,
        description: str | None = None,
    ) -> AiUsageLedgerEntry:
        if reservation_entry.status not in ("reserved", "outcome_unknown"):
            raise InvalidReservationStateError(f"Cannot settle reservation in '{reservation_entry.status}' state")

        if min(actual_audio_seconds, actual_input_tokens, actual_output_tokens, actual_cost_micros) < 0:
            raise InvalidReservationStateError("Actual provider usage must be non-negative")

        ts = now or datetime.now(timezone.utc)

        # Deduct reserved amounts from account reserved pool
        self.reserved_audio_seconds = max(0, self.reserved_audio_seconds - reservation_entry.audio_seconds)
        self.reserved_input_tokens = max(0, self.reserved_input_tokens - reservation_entry.input_tokens)
        self.reserved_output_tokens = max(0, self.reserved_output_tokens - reservation_entry.output_tokens)
        self.reserved_cost_micros = max(0, self.reserved_cost_micros - reservation_entry.cost_micros)

        # Increment used amounts with actuals
        self.used_audio_seconds += actual_audio_seconds
        self.used_input_tokens += actual_input_tokens
        self.used_output_tokens += actual_output_tokens
        self.used_cost_micros += actual_cost_micros
        self.updated_at = ts

        # Update reservation status
        reservation_entry.status = "settled"
        reservation_entry.settled_at = ts

        return AiUsageLedgerEntry(
            id=entry_id or str(uuid.uuid4()),
            account_id=self.id,
            job_id=reservation_entry.job_id,
            user_id=reservation_entry.user_id,
            idempotency_key=f"settle:{reservation_entry.idempotency_key}:{attempt}",
            kind="settlement",
            status="settled",
            provider=reservation_entry.provider,
            provider_request_id=provider_request_id,
            attempt=attempt,
            audio_seconds=actual_audio_seconds,
            input_tokens=actual_input_tokens,
            output_tokens=actual_output_tokens,
            cost_micros=actual_cost_micros,
            currency=reservation_entry.currency,
            policy_version=self.policy_version,
            created_at=ts,
            settled_at=ts,
            description=description,
        )

    def release(
        self,
        reservation_entry: AiUsageLedgerEntry,
        entry_id: str | None = None,
        now: datetime | None = None,
        reason: str | None = None,
    ) -> AiUsageLedgerEntry:
        if reservation_entry.status != "reserved":
            raise InvalidReservationStateError(f"Cannot release reservation in '{reservation_entry.status}' state")

        ts = now or datetime.now(timezone.utc)
        self.reserved_audio_seconds = max(0, self.reserved_audio_seconds - reservation_entry.audio_seconds)
        self.reserved_input_tokens = max(0, self.reserved_input_tokens - reservation_entry.input_tokens)
        self.reserved_output_tokens = max(0, self.reserved_output_tokens - reservation_entry.output_tokens)
        self.reserved_cost_micros = max(0, self.reserved_cost_micros - reservation_entry.cost_micros)
        self.updated_at = ts

        reservation_entry.status = "released"
        reservation_entry.settled_at = ts

        return AiUsageLedgerEntry(
            id=entry_id or str(uuid.uuid4()),
            account_id=self.id,
            job_id=reservation_entry.job_id,
            user_id=reservation_entry.user_id,
            idempotency_key=f"release:{reservation_entry.idempotency_key}",
            kind="release",
            status="released",
            provider=reservation_entry.provider,
            provider_request_id=None,
            attempt=reservation_entry.attempt,
            audio_seconds=0,
            input_tokens=0,
            output_tokens=0,
            cost_micros=0,
            currency=reservation_entry.currency,
            policy_version=self.policy_version,
            created_at=ts,
            settled_at=ts,
            description=reason,
        )

    def reconcile(
        self,
        reservation_entry: AiUsageLedgerEntry,
        status: str,
        entry_id: str | None = None,
        now: datetime | None = None,
        reason: str | None = None,
    ) -> AiUsageLedgerEntry:
        ts = now or datetime.now(timezone.utc)
        reservation_entry.status = status
        reservation_entry.settled_at = ts

        return AiUsageLedgerEntry(
            id=entry_id or str(uuid.uuid4()),
            account_id=self.id,
            job_id=reservation_entry.job_id,
            user_id=reservation_entry.user_id,
            idempotency_key=f"reconcile:{reservation_entry.idempotency_key}",
            kind="reconciliation",
            status=status,
            provider=reservation_entry.provider,
            provider_request_id=reservation_entry.provider_request_id,
            attempt=reservation_entry.attempt,
            audio_seconds=reservation_entry.audio_seconds,
            input_tokens=reservation_entry.input_tokens,
            output_tokens=reservation_entry.output_tokens,
            cost_micros=reservation_entry.cost_micros,
            currency=reservation_entry.currency,
            policy_version=self.policy_version,
            created_at=ts,
            settled_at=ts,
            description=reason,
        )
