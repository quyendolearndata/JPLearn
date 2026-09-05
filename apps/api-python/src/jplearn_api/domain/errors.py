"""Domain errors taxonomy (Pure Python, zero external dependencies)."""

from __future__ import annotations


class DomainError(Exception):
    """Base exception for all business domain errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EntityNotFoundError(DomainError):
    """Raised when an entity requested by ID does not exist."""


class ConflictError(DomainError):
    """Raised when a unique constraint or concurrency conflict occurs."""


class DuplicateEmailError(ConflictError):
    """Raised when attempting to register with an existing email."""


class InvalidDomainStateError(DomainError):
    """Raised when an entity operation is invalid in its current state."""


class SessionAlreadyEndedError(InvalidDomainStateError):
    """Raised when attempting to terminate an already ended session."""


class UnauthorizedError(DomainError):
    """Raised when authentication credentials or token are invalid."""


class ForbiddenError(DomainError):
    """Raised when authenticated user lacks authorization for the operation."""


class MediaInvariantError(DomainError):
    """Raised when a media asset violates publish or playback invariants."""
