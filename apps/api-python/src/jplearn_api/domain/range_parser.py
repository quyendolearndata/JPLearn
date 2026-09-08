"""HTTP byte range parser per RFC 7233 / RFC 9110 (Pure Python Domain Policy)."""

from __future__ import annotations

from jplearn_api.domain.media import RangeNotSatisfiableError

RangeNotSatisfiable = RangeNotSatisfiableError


def parse_byte_range(range_header: str | None, total_size: int) -> tuple[int, int, int] | None:
    """Parse HTTP Range header for single byte range per RFC 7233 / RFC 9110.

    Returns (start, end, length) if a valid satisfiable single range is requested.
    Returns None if Range header is missing, or contains multiple ranges / unsupported units (falls back to 200).
    Raises RangeNotSatisfiableError if range is unsatisfiable (HTTP 416).
    """
    if not range_header or not range_header.strip():
        return None

    range_header = range_header.strip()
    if not range_header.startswith("bytes="):
        # Ignore unsupported range unit per RFC 7233 §3.1
        return None

    specs = range_header[len("bytes=") :].strip()
    # RFC 7233 §3.1: server supporting range requests MAY ignore multiple ranges and serve full 200 response
    if "," in specs:
        return None

    if total_size <= 0:
        raise RangeNotSatisfiableError(total_size)

    if specs.startswith("-"):
        # Suffix range: bytes=-suffix
        suffix_str = specs[1:].strip()
        if not suffix_str.isdigit():
            return None
        suffix = int(suffix_str)
        if suffix <= 0:
            raise RangeNotSatisfiableError(total_size)
        if suffix >= total_size:
            start = 0
        else:
            start = total_size - suffix
        end = total_size - 1
        return (start, end, end - start + 1)

    if "-" not in specs:
        return None

    start_str, end_str = specs.split("-", 1)
    start_str = start_str.strip()
    end_str = end_str.strip()

    if not start_str.isdigit():
        return None

    start = int(start_str)
    if start >= total_size:
        raise RangeNotSatisfiableError(total_size)

    if not end_str:
        # Open-ended: bytes=start-
        end = total_size - 1
    else:
        if not end_str.isdigit():
            return None
        end = int(end_str)
        if start > end:
            raise RangeNotSatisfiableError(total_size)
        if end >= total_size:
            end = total_size - 1

    return (start, end, end - start + 1)
