"""Japanese scene search domain logic (Pure Python, zero external dependencies)."""

from __future__ import annotations

import base64
import json
import re
import unicodedata
from typing import Literal

from jplearn_api.domain.errors import ValidationError
from jplearn_api.domain.transcript import analyze_japanese_text


def normalize_search_query(q: str) -> str:
    """Normalize Japanese search query using Unicode NFKC and strip whitespaces.

    Validates that query length is between 1 and 100 characters.
    """
    if not q:
        raise ValidationError("Search query must not be empty (1-100 characters)")

    normalized = unicodedata.normalize("NFKC", q).strip()
    if len(normalized) < 1 or len(normalized) > 100:
        raise ValidationError(f"Search query length must be between 1 and 100 characters (got {len(normalized)})")
    return normalized


def search_candidate_terms(query: str) -> list[str]:
    """Return literal terms suitable for narrowing candidates in persistence."""
    words = [word for word in re.split(r"[\s\u3000、。！？「」『』（）()【】…,\.!?]+", query) if word]
    if len(words) > 1:
        return list(dict.fromkeys(words))
    tokens = [
        token.surface
        for token in analyze_japanese_text(query)
        if token.char_type in ("kanji", "hiragana", "katakana", "latin", "number")
    ]
    return list(dict.fromkeys(tokens))


def calculate_highlights_and_match_kind(
    text_ja: str,
    query: str,
) -> tuple[Literal["exact_phrase", "token_match"] | None, list[dict[str, int]]]:
    """Identify match kind and character highlight spans with Unicode code point offsets.

    Priority 1: exact_phrase match
    Priority 2: token_match (all main lexical tokens present in text)
    """
    norm_q = unicodedata.normalize("NFKC", query).strip()
    if not norm_q or not text_ja:
        return None, []

    # 1. Exact phrase match
    if norm_q in text_ja:
        spans: list[dict[str, int]] = []
        q_len = len(norm_q)
        start = 0
        while True:
            idx = text_ja.find(norm_q, start)
            if idx == -1:
                break
            spans.append({"start_offset": idx, "end_offset": idx + q_len})
            start = idx + max(1, q_len)
        return "exact_phrase", spans

    # 2. Token match
    words = [w for w in re.split(r"[\s\u3000、。！？「」『』（）()【】…,\.!?]+", norm_q) if w]
    if len(words) > 1 and all(w in text_ja for w in words):
        matched_tokens = words
    else:
        tokens = [
            t.surface
            for t in analyze_japanese_text(norm_q)
            if t.char_type in ("kanji", "hiragana", "katakana", "latin", "number")
        ]
        if not tokens:
            return None, []
        matched_tokens = [tok for tok in tokens if tok in text_ja]
        if len(matched_tokens) < len(tokens):
            return None, []

    token_spans: list[dict[str, int]] = []
    for tok in matched_tokens:
        tok_len = len(tok)
        start = 0
        while True:
            idx = text_ja.find(tok, start)
            if idx == -1:
                break
            token_spans.append({"start_offset": idx, "end_offset": idx + tok_len})
            start = idx + max(1, tok_len)

    # Sort spans by start_offset and merge overlapping
    token_spans.sort(key=lambda s: (s["start_offset"], s["end_offset"]))
    merged_spans: list[dict[str, int]] = []
    for sp in token_spans:
        if not merged_spans:
            merged_spans.append(sp)
        else:
            last = merged_spans[-1]
            if sp["start_offset"] <= last["end_offset"]:
                last["end_offset"] = max(last["end_offset"], sp["end_offset"])
            else:
                merged_spans.append(sp)

    return "token_match", merged_spans


def encode_search_cursor(generation: str, offset: int) -> str:
    """Encode search pagination cursor with index generation pin."""
    payload = json.dumps({"gen": generation, "offset": offset})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_search_cursor(cursor: str) -> tuple[str, int]:
    """Decode search pagination cursor, extracting index generation and offset."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        data = json.loads(raw)
        gen = str(data["gen"])
        offset = int(data["offset"])
        if offset < 0:
            raise ValueError("Offset must be non-negative")
        return gen, offset
    except Exception as exc:
        raise ValidationError("Invalid search cursor format") from exc
