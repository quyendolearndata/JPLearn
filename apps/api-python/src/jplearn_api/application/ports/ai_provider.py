"""Ports and interfaces for external AI speech-to-text and segmentation services (ADR-007 PR8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AiUsageRecord:
    """Usage consumption metadata returned by AI provider."""

    audio_seconds: int
    input_tokens: int
    output_tokens: int
    cost_micros: int
    provider_request_id: str
    currency: str = "USD"
    policy_version: str = "v1"


@dataclass(frozen=True)
class AiTranscriptionResult:
    """Standardized output from an AI transcription & segmentation job."""

    segments: list[dict[str, Any]]
    usage: AiUsageRecord
    provenance: dict[str, Any] = field(default_factory=dict)


class AiTranscriptionPort(Protocol):
    """Abstraction for AI transcription providers."""

    async def transcribe_and_segment(
        self,
        media_storage_key: str,
        media_duration_seconds: int,
        language: str = "ja",
    ) -> AiTranscriptionResult:
        """Process media audio file, returning transcript segments and operational usage."""
        ...
