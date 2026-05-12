"""공개 클라이언트에서 쓰는 작은 변환 헬퍼."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def without_none(values: Mapping[str, Any]) -> dict[str, Any]:
    """값이 None이 아닌 항목만 담은 dict를 반환합니다."""

    return {key: value for key, value in values.items() if value is not None}


def strip_or_none(value: object) -> str | None:
    """공백을 제거한 문자열을 반환하고, 빈 값이면 None을 반환합니다."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def csv_or_none(value: object) -> str | None:
    """list 계열 query parameter를 쉼표 구분 문자열로 반환합니다."""

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
    """날짜 형태 값을 YYYYMMDD 문자열로 정규화합니다."""

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
    """흔한 KHOA 날짜/시간 문자열을 Asia/Seoul datetime으로 파싱합니다."""

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
