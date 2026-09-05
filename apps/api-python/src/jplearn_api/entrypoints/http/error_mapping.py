"""HTTP error mapping from Domain errors to HTTP responses (ADR-005/ADR-006)."""

from __future__ import annotations

from fastapi import HTTPException

from jplearn_api.domain.errors import (
    ConflictError,
    DomainError,
    DuplicateEmailError,
    EntityNotFoundError,
    ForbiddenError,
    InvalidDomainStateError,
    MediaInvariantError,
    SessionAlreadyEndedError,
    UnauthorizedError,
)
from jplearn_api.domain.range_parser import RangeNotSatisfiableError


def map_domain_error_to_http(exc: DomainError) -> HTTPException:
    """Map pure Python domain errors to HTTP exceptions adhering to ADR-005 contract."""
    if isinstance(exc, RangeNotSatisfiableError):
        return HTTPException(
            status_code=416,
            detail="Range Not Satisfiable",
            headers={
                "Content-Range": f"bytes */{exc.total_size}",
                "Accept-Ranges": "bytes",
                "X-Content-Type-Options": "nosniff",
            },
        )
    if isinstance(exc, DuplicateEmailError):
        return HTTPException(status_code=409, detail="Email already registered")
    if isinstance(exc, SessionAlreadyEndedError):
        return HTTPException(status_code=400, detail="Session already ended")
    if isinstance(exc, EntityNotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=exc.message)
    if isinstance(exc, UnauthorizedError):
        return HTTPException(status_code=401, detail=exc.message or "Unauthorized")
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=403, detail=exc.message or "Forbidden")
    if isinstance(exc, (InvalidDomainStateError, MediaInvariantError)):
        return HTTPException(status_code=400, detail=exc.message)
    return HTTPException(status_code=400, detail=exc.message)
