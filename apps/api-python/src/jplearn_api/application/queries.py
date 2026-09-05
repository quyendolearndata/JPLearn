"""Application queries (Pure Python dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetFlagsQuery:
    pass
