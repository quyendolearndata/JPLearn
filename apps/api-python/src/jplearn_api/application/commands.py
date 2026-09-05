"""Application commands (Pure Python dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateFlagsCommand:
    flags: dict[str, bool]
