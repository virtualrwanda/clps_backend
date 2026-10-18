"""
Timezone helpers.

Legacy timestamp values may be returned as
naive datetimes. Our code wants UTC-aware datetimes. This module bridges
the gap so comparisons don't raise
    TypeError: can't compare offset-naive and offset-aware datetimes
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware UTC now. Use this everywhere instead of datetime.utcnow()."""
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """
    Normalize a datetime to UTC-aware.

    - None           -> None
    - aware dt       -> converted to UTC
    - naive dt       -> assumed UTC (safe: we always write UTC on insert)
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_past(dt: datetime | None) -> bool:
    """True if dt (naive or aware) is in the past relative to UTC now."""
    if dt is None:
        return False
    return as_utc(dt) <= utcnow()