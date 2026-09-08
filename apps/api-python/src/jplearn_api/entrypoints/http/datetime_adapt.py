from datetime import UTC, datetime


def to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(tzinfo=None)


def from_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_json_z(dt: datetime) -> str:
    aware = from_naive_utc(dt)
    if aware is None:
        raise ValueError("datetime required")
    return aware.isoformat(timespec="milliseconds").replace("+00:00", "Z")
