from __future__ import annotations

import re

_PATTERNS = [
    # password / password_hash / token / secret key-value assignments
    (re.compile(r"(['\"]?(?:password(?:_hash)?|secret|token|credential)['\"]?\s*[:=]\s*['\"]?)(?:[^'\",\s\\]|\\.)+(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\2"),
    # Bearer tokens
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE), r"\1[REDACTED]"),
    # JWT tokens
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+\b"), "[REDACTED_JWT]"),
    # Argon2 hashes
    (re.compile(r"\$argon2id\$[^\s'\",]+"), "[REDACTED_HASH]"),
    # Database connection strings with credentials
    (re.compile(r"(postgres(?:ql)?(?:\+asyncpg)?://)[^:]+:[^@]+@"), r"\1[REDACTED]@"),
]


def sanitize_message(message: str) -> str:
    """Redact passwords, hashes, tokens and connection secrets from messages."""
    sanitized = message
    for pattern, replacement in _PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized
