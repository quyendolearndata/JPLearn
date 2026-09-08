"""Measured source inspection contract; adapters own media tools and filesystem I/O."""
from dataclasses import dataclass

@dataclass(frozen=True)
class MediaInspection:
    duration_ms: int
    sha256: str
