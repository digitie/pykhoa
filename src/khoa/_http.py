"""data.go.kr를 통해 제공되는 KHOA ODMI API HTTP 헬퍼."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Protocol, TypeVar, cast
from xml.etree import ElementTree

import httpx

from ._convert import normalize_service_key, without_none
from .exceptions import (
    KhoaAuthError,
    KhoaParseError,
    KhoaRateLimitError,
    KhoaRequestError,
    KhoaServerError,
)
from .services import DEFAULT_BASE_URL, ServiceDefinition


class ResponseLike(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...

    def json(self) -> Any: ...


class SessionLike(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        timeout: float,
    ) -> ResponseLike | Awaitable[ResponseLike]: ...


TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
DEFAULT_USER_AGENT = "python-khoa-api/0.1 (+https://www.khoa.go.kr/oceandata/openapi/odmi)"
DEFAULT_MAX_RPS = 5.0
R = TypeVar("R")


def run_async(awaitable_factory: Callable[[], Coroutine[Any, Any, R]]) -> R:
    """동기 facade에서 async 구현을 실행합니다."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable_factory())

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(awaitable_factory())).result()


def build_session(retries: int = 3, *, timeout: float = 10.0) -> SessionLike:
    """호환성을 위해 httpx AsyncClient 세션을 만듭니다."""

    del retries
    return cast(
        SessionLike,
        httpx.AsyncClient(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        ),
    )


class AsyncTokenBucket:
    """단순 async 토큰 버킷 속도 제한기."""

    def __init__(self, max_rps: float = DEFAULT_MAX_RPS) -> None:
        if max_rps <= 0:
            raise ValueError("max_rps must be greater than 0")
        self.max_rps = max_rps
        self.capacity = max_rps
        self._tokens = max_rps
        self._updated_at = time.monotonic()
        self._lock = Lock()

    async def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._updated_at
                self._updated_at = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self.max_rps)
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait_for = (1 - self._tokens) / self.max_rps
            await asyncio.sleep(wait_for)


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
        max_rps: float = DEFAULT_MAX_RPS,
    ) -> None:
        key = normalize_service_key(service_key)
        if not key:
            raise KhoaAuthError("service_key is required", failure_kind="auth")
        self.service_key = key
        self.base_url = base_url.rstrip("/")
        self.service_key_param = service_key_param
        self.session = session
        self.timeout = timeout
        self.retries = retries
        self._bucket = AsyncTokenBucket(max_rps)

    def get(
        self,
        service: ServiceDefinition,
        params: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], str]:
        """서비스를 호출하고 디코딩된 JSON payload와 요청 URL을 반환합니다."""

        return run_async(lambda: self.aget(service, params))

    async def aget(
        self,
        service: ServiceDefinition,
        params: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], str]:
        """서비스를 비동기로 호출하고 디코딩된 JSON payload와 요청 URL을 반환합니다."""

        url = f"{self.base_url}/{service.endpoint}"
        request_params = {self.service_key_param: self.service_key, **dict(params)}
        response = await self._request_with_retries(
            url,
            request_params,
            endpoint=service.endpoint,
            service_key=self.service_key,
        )
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

    def get_url(
        self,
        url: str,
        params: Mapping[str, Any],
        *,
        endpoint: str,
        service_key: str | None = None,
    ) -> tuple[Mapping[str, Any], str]:
        """서비스 정의 밖의 JSON URL을 호출합니다."""

        return run_async(
            lambda: self.aget_url(
                url,
                params,
                endpoint=endpoint,
                service_key=service_key,
            )
        )

    async def aget_url(
        self,
        url: str,
        params: Mapping[str, Any],
        *,
        endpoint: str,
        service_key: str | None = None,
    ) -> tuple[Mapping[str, Any], str]:
        """서비스 정의 밖의 JSON URL을 비동기로 호출합니다."""

        redaction_key = service_key or self.service_key
        response = await self._request_with_retries(
            url,
            params,
            endpoint=endpoint,
            service_key=redaction_key,
        )
        _raise_for_status(response, endpoint=endpoint, service_key=redaction_key)
        try:
            payload = response.json()
        except ValueError as exc:
            _raise_for_xml_error(
                response.text,
                endpoint=endpoint,
                service_key=redaction_key,
            )
            message = _redact_secret(str(exc), redaction_key)
            raise KhoaParseError(
                f"KHOA response was not valid JSON: {message}",
                endpoint=endpoint,
                failure_kind="parse",
            ) from exc
        if not isinstance(payload, Mapping):
            raise KhoaParseError(
                "KHOA JSON root was not an object",
                endpoint=endpoint,
                failure_kind="parse",
            )
        return payload, url

    async def aclose(self) -> None:
        """외부에서 주입한 httpx async 세션이 있으면 닫습니다."""

        close = getattr(self.session, "aclose", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    def close(self) -> None:
        """동기 facade에서 세션을 닫습니다."""

        run_async(self.aclose)

    async def _request_with_retries(
        self,
        url: str,
        params: Mapping[str, Any],
        *,
        endpoint: str,
        service_key: str,
    ) -> ResponseLike:
        request_params = without_none(params)
        attempts = max(1, self.retries + 1)
        last_error: KhoaRequestError | None = None

        for attempt in range(attempts):
            await self._bucket.acquire()
            try:
                response = await self._request_once(url, request_params)
            except httpx.HTTPError as exc:
                message = _redact_secret(str(exc), service_key)
                last_error = KhoaRequestError(
                    f"HTTP transport error: {message}",
                    endpoint=endpoint,
                    failure_kind="request",
                    retryable=True,
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(_retry_wait(attempt))
                    continue
                raise last_error from exc

            if response.status_code in TRANSIENT_STATUSES and attempt < attempts - 1:
                await asyncio.sleep(_retry_wait(attempt))
                continue
            return response

        if last_error is not None:
            raise last_error
        raise AssertionError("unreachable")

    async def _request_once(self, url: str, params: Mapping[str, Any]) -> ResponseLike:
        if self.session is not None:
            result = self.session.get(url, params=params, timeout=self.timeout)
            if inspect.isawaitable(result):
                return await result
            return result

        async with httpx.AsyncClient(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            return await client.get(url, params=params)


def _retry_wait(attempt: int) -> float:
    return min(8.0, 2.0**attempt)


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
