"""데이터소스별 서비스키 로딩 유틸리티."""

from __future__ import annotations

import os
from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import Final

from ._convert import normalize_service_key
from .exceptions import KhoaAuthError

DATA_GO_KR_ENV_NAMES: Final = (
    "KHOA_DATA_GO_KR_SERVICE_KEY",
    "KHOA_SERVICE_KEY",
    "DATA_GO_KR_SERVICE_KEY",
    "PUBLIC_DATA_SERVICE_KEY",
    "TRIPMATE_DATA_GO_SERVICE_KEY",
    "KHOA_API_KEY",
)
KHOA_GO_KR_ENV_NAMES: Final = (
    "KHOA_DIRECT_SERVICE_KEY",
    "KHOA_GO_KR_SERVICE_KEY",
    "KHOA_BEACH_SEARCH_SERVICE_KEY",
    "TRIPMATE_KHOA_API_KEY",
    "KHOA_API_KEY",
)
VWORLD_ENV_NAMES: Final = (
    "VWORLD_API_KEY",
    "VWORLD_SERVICE_KEY",
    "VWORLD_KEY",
)
SERVICE_KEY_ENV_NAMES_BY_SOURCE: Final[dict[str, tuple[str, ...]]] = {
    "data.go.kr": DATA_GO_KR_ENV_NAMES,
    "khoa.go.kr": KHOA_GO_KR_ENV_NAMES,
    "vworld": VWORLD_ENV_NAMES,
}


def get_service_key(
    source: str = "data.go.kr",
    *,
    env_file: str | PathLike[str] | None = ".env",
    names: tuple[str, ...] | None = None,
    required: bool = False,
) -> str | None:
    """데이터소스별 환경변수와 `.env`에서 서비스키를 찾습니다."""

    env_names = names or _env_names_for_source(source)
    key = _first_process_env(env_names) or _first_env_file(env_names, env_file)
    if key is None and required:
        joined = ", ".join(env_names)
        raise KhoaAuthError(
            f"none of these {source} service key variables are set: {joined}",
            provider=source,
            failure_kind="auth",
        )
    return key


def load_env_file(path: str | PathLike[str]) -> dict[str, str]:
    """간단한 KEY=VALUE 형식의 `.env` 파일을 읽습니다."""

    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        clean_key = key.strip()
        clean_value = _strip_env_value(value)
        if clean_key:
            values[clean_key] = clean_value
    return values


def _env_names_for_source(source: str) -> tuple[str, ...]:
    try:
        return SERVICE_KEY_ENV_NAMES_BY_SOURCE[source]
    except KeyError as exc:
        known = ", ".join(SERVICE_KEY_ENV_NAMES_BY_SOURCE)
        raise KeyError(f"unknown service key source {source!r}; known sources: {known}") from exc


def _first_process_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = normalize_service_key(os.getenv(name))
        if value:
            return value
    return None


def _first_env_file(names: tuple[str, ...], env_file: str | PathLike[str] | None) -> str | None:
    if env_file is None:
        return None
    values = load_env_file(env_file)
    return _first_mapping_value(values, names)


def _first_mapping_value(values: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = normalize_service_key(values.get(name))
        if value:
            return value
    return None


def _strip_env_value(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text
