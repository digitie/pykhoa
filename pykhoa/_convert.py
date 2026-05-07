"""Small conversion helpers used by the public client."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def without_none(values: Mapping[str, Any]) -> dict[str, Any]:
    """Return a dict with keys whose value is not None."""

    return {key: value for key, value in values.items() if value is not None}


def strip_or_none(value: object) -> str | None:
    """Return stripped text, or None for empty values."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def csv_or_none(value: object) -> str | None:
    """Return a comma-separated string for list-like query parameters."""

    if value is None:
        return None
    if isinstance(value, str):
        return strip_or_none(value)
    if isinstance(value, tuple | list | set):
        items = [str(item).strip() for item in value if str(item).strip()]
        return ",".join(items) if items else None
    return strip_or_none(value)


def to_int_or_none(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def to_float_or_none(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_yyyymmdd(value: str | date | datetime | None, *, field: str) -> str | None:
    """Normalize a date-like value to YYYYMMDD."""

    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(KST).strftime("%Y%m%d")
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text.replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"{field} must be YYYYMMDD or YYYY-MM-DD")
    return text


def to_datetime_or_none(value: object) -> datetime | None:
    """Parse common KHOA date-time strings as Asia/Seoul datetimes."""

    text = strip_or_none(value)
    if text is None:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
        "%Y%m%d",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=KST)
    return None
