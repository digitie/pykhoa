"""data.go.kr를 통해 제공되는 KHOA ODMI API HTTP 헬퍼."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast
from xml.etree import ElementTree

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ._convert import without_none
from .exceptions import (
    KhoaAuthError,
    KhoaParseError,
    KhoaRateLimitError,
    KhoaRequestError,
    KhoaServerError,
)
from .services import DEFAULT_BASE_URL, ServiceDefinition


class ResponseLike(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class SessionLike(Protocol):
    def get(self, url: str, *, params: Mapping[str, Any], timeout: float) -> ResponseLike: ...


TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
DEFAULT_USER_AGENT = "python-khoa-api/0.1 (+https://www.khoa.go.kr/oceandata/openapi/odmi)"


def build_session(retries: int = 3) -> SessionLike:
    """보수적인 GET 재시도를 설정한 requests 세션을 만듭니다."""

    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
    if retries <= 0:
        return cast(SessionLike, session)

    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.3,
        status_forcelist=tuple(sorted(TRANSIENT_STATUSES)),
        allowed_methods=frozenset({"GET"}),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return cast(SessionLike, session)


class KhoaHttp:
    """KHOA ODMI 엔드포인트용 저수준 JSON HTTP 클라이언트."""

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        service_key_param: str = "serviceKey",
        session: SessionLike | None = None,
        timeout: float = 10.0,
        retries: int = 3,
    ) -> None:
        if not service_key:
            raise KhoaAuthError("service_key is required", failure_kind="auth")
        self.service_key = service_key
        self.base_url = base_url.rstrip("/")
        self.service_key_param = service_key_param
        self.session = session or build_session(retries)
        self.timeout = timeout

    def get(
        self,
        service: ServiceDefinition,
        params: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], str]:
        """서비스를 호출하고 디코딩된 JSON payload와 요청 URL을 반환합니다."""

        url = f"{self.base_url}/{service.endpoint}"
        request_params = {self.service_key_param: self.service_key, **dict(params)}
        response = self.session.get(url, params=without_none(request_params), timeout=self.timeout)
        _raise_for_status(response, endpoint=service.endpoint, service_key=self.service_key)
        try:
            payload = response.json()
        except ValueError as exc:
            _raise_for_xml_error(
                response.text,
                endpoint=service.endpoint,
                service_key=self.service_key,
            )
            message = _redact_secret(str(exc), self.service_key)
            raise KhoaParseError(
                f"KHOA response was not valid JSON: {message}",
                endpoint=service.endpoint,
                service=service.key,
                failure_kind="parse",
            ) from exc
        if not isinstance(payload, Mapping):
            raise KhoaParseError(
                "KHOA JSON root was not an object",
                endpoint=service.endpoint,
                service=service.key,
                failure_kind="parse",
            )
        return payload, url


def _raise_for_status(response: ResponseLike, *, endpoint: str, service_key: str) -> None:
    status = response.status_code
    text = _redact_secret(response.text, service_key)[:300]
    if status in {401, 403}:
        raise KhoaAuthError(
            f"HTTP {status}: {text}",
            endpoint=endpoint,
            status_code=status,
            failure_kind="auth",
            retryable=False,
        )
    if status == 429:
        raise KhoaRateLimitError(
            f"HTTP {status}: {text}",
            endpoint=endpoint,
            status_code=status,
            failure_kind="rate_limit",
            retryable=True,
        )
    if 400 <= status < 500:
        raise KhoaRequestError(
            f"HTTP {status}: {text}",
            endpoint=endpoint,
            status_code=status,
            failure_kind="request",
            retryable=False,
        )
    if 500 <= status < 600:
        raise KhoaServerError(
            f"HTTP {status}: {text}",
            endpoint=endpoint,
            status_code=status,
            failure_kind="server",
            retryable=True,
        )


def _raise_for_xml_error(text: str, *, endpoint: str, service_key: str) -> None:
    text = text.strip()
    if not text.startswith("<"):
        return
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return

    values: dict[str, str] = {}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if element.text and element.text.strip():
            values[tag] = element.text.strip()

    code = values.get("returnReasonCode") or values.get("resultCode") or ""
    message = (
        values.get("returnAuthMsg")
        or values.get("errMsg")
        or values.get("resultMsg")
        or "KHOA XML error response"
    )
    _raise_for_result_code(code, message, endpoint=endpoint, service_key=service_key)


def _raise_for_result_code(
    code: str,
    message: str,
    *,
    endpoint: str,
    service_key: str | None = None,
) -> None:
    text = _redact_secret(f"KHOA API returned {code}: {message}" if code else message, service_key)
    upper = text.upper()
    if code in {"20", "30", "31"} or "SERVICE_KEY" in upper or "AUTH" in upper:
        raise KhoaAuthError(text, endpoint=endpoint, result_code=code, failure_kind="auth")
    if code == "22" or "LIMIT" in upper or "QUOTA" in upper or "TRAFFIC" in upper:
        raise KhoaRateLimitError(
            text,
            endpoint=endpoint,
            result_code=code,
            failure_kind="rate_limit",
        )
    if code in {"04", "99"} or code.startswith("5"):
        raise KhoaServerError(text, endpoint=endpoint, result_code=code, failure_kind="server")
    raise KhoaRequestError(text, endpoint=endpoint, result_code=code, failure_kind="request")


def _redact_secret(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")
