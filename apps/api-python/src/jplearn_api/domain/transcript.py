"""Domain models and rules for Japanese Transcripts and Language Analysis (ADR-007 PR8a).

Enforces:
- FR-JPA-001 / UC-T10: Japanese transcript workflow with revisions, CAS concurrency, provenance.
- Validation limits: <= 100 segments/clip, <= 500 chars/segment, <= 20,000 total chars.
- Content version alignment: every segment must map to a valid scene in the version.
- Transition rules: draft -> qa_submitted -> approved / returned_to_draft.
- Pure-Python Unicode code point analyzer (Kanji, Hiragana, Katakana, Latin, Number, Punctuation).
- Zero banned textbook/grammar pedagogy exposure (FR-NEG).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from jplearn_api.domain.errors import InvalidDomainStateError, ValidationError

MAX_SEGMENTS_PER_CLIP = 100
MAX_CHARS_PER_SEGMENT = 500
MAX_TOTAL_CHARS_PER_CLIP = 20_000


class TranscriptStatus(StrEnum):
    DRAFT = "draft"
    QA_SUBMITTED = "qa_submitted"
    APPROVED = "approved"
    RETURNED_TO_DRAFT = "returned_to_draft"


class TranscriptProvenance(StrEnum):
    MANUAL_TEACHER = "manual_teacher"
    AI_ASSISTED = "ai_assisted"
    IMPORTED = "imported"


class LanguageAnalysisJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class TranscriptSegment:
    scene_id: str
    text_ja: str

    def validate(self) -> None:
        if not self.scene_id or not self.scene_id.strip():
            raise ValidationError("scene_id cannot be empty")
        if len(self.text_ja) > MAX_CHARS_PER_SEGMENT:
            raise ValidationError(
                f"Segment text exceeds maximum length of {MAX_CHARS_PER_SEGMENT} characters (got {len(self.text_ja)})"
            )


@dataclass
class TranscriptRevision:
    id: str
    catalog_item_id: str
    content_version_id: str
    revision: int
    status: TranscriptStatus
    segments: list[TranscriptSegment]
    provenance: TranscriptProvenance
    created_by: str
    approved_by: str | None = None
    return_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def validate_bounds(self) -> None:
        if len(self.segments) > MAX_SEGMENTS_PER_CLIP:
            raise ValidationError(
                f"Transcript has {len(self.segments)} segments, exceeding limit of {MAX_SEGMENTS_PER_CLIP}"
            )
        total_chars = 0
        scene_ids: set[str] = set()
        for seg in self.segments:
            seg.validate()
            if seg.scene_id in scene_ids:
                raise ValidationError(f"Duplicate scene_id '{seg.scene_id}' in transcript segments")
            scene_ids.add(seg.scene_id)
            total_chars += len(seg.text_ja)

        if total_chars > MAX_TOTAL_CHARS_PER_CLIP:
            raise ValidationError(
                f"Total transcript length ({total_chars} chars) exceeds maximum allowed {MAX_TOTAL_CHARS_PER_CLIP}"
            )

    def submit_qa(self) -> None:
        if self.status not in (TranscriptStatus.DRAFT, TranscriptStatus.RETURNED_TO_DRAFT):
            raise InvalidDomainStateError(f"Cannot submit QA from status '{self.status.value}'")
        self.validate_bounds()
        self.status = TranscriptStatus.QA_SUBMITTED
        self.return_reason = None

    def approve(self, approver_user_id: str) -> None:
        if self.status != TranscriptStatus.QA_SUBMITTED:
            raise InvalidDomainStateError(
                f"Cannot approve transcript from status '{self.status.value}', must be 'qa_submitted'"
            )
        self.status = TranscriptStatus.APPROVED
        self.approved_by = approver_user_id
        self.return_reason = None

    def return_to_draft(self, reason: str) -> None:
        if self.status not in (TranscriptStatus.QA_SUBMITTED, TranscriptStatus.APPROVED):
            raise InvalidDomainStateError(f"Cannot return transcript to draft from status '{self.status.value}'")
        if not reason or not reason.strip():
            raise ValidationError("A reason must be provided when returning a transcript to draft")
        self.status = TranscriptStatus.RETURNED_TO_DRAFT
        self.return_reason = reason.strip()


@dataclass
class ApprovedSceneText:
    id: str
    catalog_item_id: str
    content_version_id: str
    scene_id: str
    transcript_revision_id: str
    text_ja: str
    scene_index: int
    start_time_seconds: int
    end_time_seconds: int
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class LanguageAnalysisJob:
    id: str
    catalog_item_id: str
    transcript_revision_id: str
    idempotency_key: str | None
    status: LanguageAnalysisJobStatus
    results: dict[str, Any] | None
    error_message: str | None
    created_by: str
    created_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class TokenSpan:
    surface: str
    char_type: str
    start_offset: int
    end_offset: int
    reading_hint: str | None = None
    lemma: str | None = None


def get_char_type(ch: str) -> str:
    code = ord(ch)
    if (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF):
        return "kanji"
    if 0x3040 <= code <= 0x309F:
        return "hiragana"
    if 0x30A0 <= code <= 0x30FF:
        return "katakana"
    if ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
        return "latin"
    if "0" <= ch <= "9" or (0xFF10 <= code <= 0xFF19):
        return "number"
    if ch in " \t\r\n\u3000":
        return "whitespace"
    if ch in "、。！？「」『』（）()【】[]…―—,.-!?:;":
        return "punct"
    cat = unicodedata.category(ch)
    if cat.startswith("P") or cat.startswith("S"):
        return "punct"
    return "other"


def analyze_japanese_text(text: str) -> list[TokenSpan]:
    """Tokenize and extract character spans with Unicode code point offsets.

    Groups contiguous runs of the same character type, preserving exact Unicode
    code point boundaries for accurate front-end highlighting.
    """
    if not text:
        return []

    spans: list[TokenSpan] = []
    chars = list(text)
    n = len(chars)
    i = 0

    while i < n:
        ctype = get_char_type(chars[i])
        j = i + 1
        # For kanji, single character or compounds can be grouped
        while j < n and get_char_type(chars[j]) == ctype:
            j += 1

        surface = "".join(chars[i:j])
        if ctype != "whitespace":
            reading_hint = surface if ctype in ("hiragana", "katakana") else None
            spans.append(
                TokenSpan(
                    surface=surface,
                    char_type=ctype,
                    start_offset=i,
                    end_offset=j,
                    reading_hint=reading_hint,
                    lemma=surface,
                )
            )
        i = j

    return spans
