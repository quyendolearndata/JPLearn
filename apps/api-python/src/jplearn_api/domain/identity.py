"""Domain entity and invariants for Identity (Pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from jplearn_api.domain.errors import InvalidDomainStateError


@dataclass
class UserAccount:
    """User account entity owning credentials, token version and roles."""

    id: str
    email: str
    password_hash: str
    token_version: int = 0
    created_at: datetime | None = None
    roles: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.email = self.normalize_email(self.email)
        if not self.email:
            raise InvalidDomainStateError("Email is required")

    @staticmethod
    def normalize_email(email: str | None) -> str:
        if not isinstance(email, str):
            return ""
        return email.strip().lower()

    def increment_token_version(self) -> None:
        """Invalidate all active sessions by incrementing token version."""
        self.token_version += 1

    def has_role(self, role: str) -> bool:
        return role in self.roles
