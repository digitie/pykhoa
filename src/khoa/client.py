"""사용자 진입점으로 제공하는 KHOA ODMI 클라이언트."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, date, datetime
from typing import Any, TypeVar

from ._convert import csv_or_none, to_int_or_none, to_yyyymmdd, without_none
from ._http import KhoaHttp, SessionLike
from .exceptions import KhoaAuthError, KhoaNoDataError, KhoaParseError, KhoaRequestError
from .models import Page, RawRecord, ResponseContext, RomsPrediction
from .services import DEFAULT_BASE_URL, SERVICE_DEFINITIONS, ServiceDefinition, get_service

DEFAULT_ENV_NAMES = (
    "KHOA_SERVICE_KEY",
    "KHOA_API_KEY",
    "DATA_GO_KR_SERVICE_KEY",
    "PUBLIC_DATA_SERVICE_KEY",
)

T = TypeVar("T")

_PARAM_ALIASES: dict[str, str] = {
    "area_code": "areaCode",
    "beach_code": "beachCode",
    "end_date": "endDate",
    "max_latitude": "ymax",
    "max_longitude": "xmax",
    "min_latitude": "ymin",
    "min_longitude": "xmin",
    "nav_route_code": "nvgtCode",
    "nvgt_code": "nvgtCode",
    "obs_code": "obsCode",
    "obs_name": "obsName",
    "page_no": "pageNo",
    "place_code": "placeCode",
    "place_name": "placeName",
    "req_date": "reqDate",
    "request_date": "reqDate",
    "sgg_cd": "sggCd",
    "start_date": "startDate",
    "vnp_code": "vnpCode",
    "x_max": "xmax",
    "x_min": "xmin",
    "y_max": "ymax",
    "y_min": "ymin",
}


class KhoaClient:
    """data.go.kr를 통해 공개된 KHOA ODMI 서비스 클라이언트."""

    def __init__(
        self,
        service_key: str | None = None,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        service_key_param: str = "serviceKey",
        timeout: float = 10.0,
        retries: int = 3,
        session: SessionLike | None = None,
    ) -> None:
        if service_key and api_key and service_key != api_key:
            raise ValueError("service_key and api_key were both provided with different values")
        key = api_key or service_key or _first_env(DEFAULT_ENV_NAMES)
        if not key:
            raise KhoaAuthError(
                "api_key is required. Pass api_key=... or set KHOA_SERVICE_KEY.",
                failure_kind="auth",
            )
        self.service_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http = KhoaHttp(
            key,
            base_url=self.base_url,
            service_key_param=service_key_param,
            session=session,
            timeout=timeout,
            retries=retries,
        )

    @classmethod
    def from_env(
        cls,
        name: str = "KHOA_SERVICE_KEY",
        *,
        fallback_names: tuple[str, ...] = DEFAULT_ENV_NAMES[1:],
        **kwargs: Any,
    ) -> KhoaClient:
        """환경변수에서 인증키를 읽어 클라이언트를 만듭니다."""

        service_key = os.getenv(name) or _first_env(fallback_names)
        if not service_key:
            names = ", ".join((name, *fallback_names))
            raise KhoaAuthError(f"none of these environment variables are set: {names}")
        return cls(api_key=service_key, **kwargs)

    @property
    def services(self) -> tuple[ServiceDefinition, ...]:
        """번들 KHOA ODMI 서비스 카탈로그를 반환합니다."""

        return SERVICE_DEFINITIONS

    def service(self, key: str | ServiceDefinition) -> ServiceDefinition:
        """key, API ID, operation, 한글 제목으로 서비스 정의 하나를 반환합니다."""

        return get_service(key)

    def __getattr__(self, name: str) -> Callable[..., Page[RawRecord]]:
        try:
            service = get_service(name)
        except KeyError as exc:
            raise AttributeError(name) from exc

        def caller(**kwargs: Any) -> Page[RawRecord]:
            return self.fetch(service, **kwargs)

        return caller

    def fetch(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        response_type: str = "json",
        include: str | tuple[str, ...] | list[str] | None = None,
        exclude: str | tuple[str, ...] | list[str] | None = None,
        validate_required: bool = True,
        **kwargs: Any,
    ) -> Page[RawRecord]:
        """임의 KHOA ODMI 서비스를 호출하고 정규화된 원문 item mapping을 반환합니다."""

        definition = get_service(service)
        request_params = self._request_params(
            definition,
            params,
            page_no=page_no,
            num_of_rows=num_of_rows,
            response_type=response_type,
            include=include,
            exclude=exclude,
            validate_required=validate_required,
            extra=kwargs,
        )
        payload, request_url = self._http.get(definition, request_params)
        body = _extract_body(payload, definition)
        rows = _extract_items(body, definition)
        return Page[RawRecord](
            items=tuple(rows),
            total_count=to_int_or_none(body.get("totalCount")) or len(rows),
            page_no=to_int_or_none(body.get("pageNo")) or page_no,
            num_of_rows=to_int_or_none(body.get("numOfRows")) or num_of_rows,
            raw=dict(body),
            context=_context(definition, request_url, request_params),
        )

    def items(self, service: str | ServiceDefinition, **kwargs: Any) -> tuple[RawRecord, ...]:
        """서비스를 호출하고 응답 item만 반환합니다."""

        return self.fetch(service, **kwargs).items

    def iter_pages(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        max_pages: int | None = None,
        max_items: int | None = None,
        **kwargs: Any,
    ) -> Iterator[Page[RawRecord]]:
        """선택적 안전 제한과 함께 KHOA 페이지 응답을 순회합니다."""

        next_page = page_no
        pages = 0
        yielded = 0
        while True:
            page = self.fetch(
                service,
                params,
                page_no=next_page,
                num_of_rows=num_of_rows,
                **kwargs,
            )
            if not page.items:
                return
            yield page
            pages += 1
            yielded += len(page.items)
            if max_pages is not None and pages >= max_pages:
                return
            if max_items is not None and yielded >= max_items:
                return
            if page.next_page_no is None:
                return
            next_page = page.next_page_no

    def roms(
        self,
        *,
        ymin: float,
        ymax: float,
        xmin: float,
        xmax: float,
        page_no: int = 1,
        num_of_rows: int = 10,
        include: str | tuple[str, ...] | list[str] | None = None,
        exclude: str | tuple[str, ...] | list[str] | None = None,
    ) -> Page[RomsPrediction]:
        """ROMS 수치예측 행을 가져와 typed 모델로 변환합니다."""

        page = self.fetch(
            "roms",
            ymin=ymin,
            ymax=ymax,
            xmin=xmin,
            xmax=xmax,
            page_no=page_no,
            num_of_rows=num_of_rows,
            include=include,
            exclude=exclude,
        )
        return Page[RomsPrediction](
            items=tuple(RomsPrediction.from_raw(row) for row in page.items),
            total_count=page.total_count,
            page_no=page.page_no,
            num_of_rows=page.num_of_rows,
            raw=page.raw,
            context=page.context,
        )

    def first(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> RawRecord:
        """첫 번째 원문 item을 반환하거나 KhoaNoDataError를 발생시킵니다."""

        page = self.fetch(service, params, **kwargs)
        if not page.items:
            definition = get_service(service)
            raise KhoaNoDataError(
                f"{definition.key} returned no items",
                endpoint=definition.endpoint,
                service=definition.key,
                failure_kind="no_data",
            )
        return page.items[0]

    def _request_params(
        self,
        definition: ServiceDefinition,
        params: Mapping[str, Any] | None,
        *,
        page_no: int,
        num_of_rows: int,
        response_type: str,
        include: str | tuple[str, ...] | list[str] | None,
        exclude: str | tuple[str, ...] | list[str] | None,
        validate_required: bool,
        extra: Mapping[str, Any],
    ) -> dict[str, Any]:
        if page_no < 1:
            raise ValueError("page_no must be >= 1")
        if not 1 <= num_of_rows <= 1000:
            raise ValueError("num_of_rows must be between 1 and 1000")

        merged: dict[str, Any] = {}
        if params:
            merged.update(params)
        merged.update(extra)
        merged["pageNo"] = page_no
        merged["numOfRows"] = num_of_rows
        merged["type"] = response_type
        if include is not None:
            merged["include"] = include
        if exclude is not None:
            merged["exclude"] = exclude

        normalized = _normalize_param_names(merged)
        normalized["include"] = csv_or_none(normalized.get("include"))
        normalized["exclude"] = csv_or_none(normalized.get("exclude"))
        _normalize_dates(normalized)
        cleaned = without_none(normalized)
        if validate_required:
            missing = [name for name in definition.required_params if not cleaned.get(name)]
            if missing:
                joined = ", ".join(missing)
                raise KhoaRequestError(
                    f"{definition.key} requires parameter(s): {joined}",
                    endpoint=definition.endpoint,
                    service=definition.key,
                    failure_kind="request",
                )
        return cleaned


KhoaODMIClient = KhoaClient


def _first_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _normalize_param_names(params: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in params.items():
        text_key = str(key)
        if text_key in {"serviceKey", "service_key"}:
            continue
        target = _PARAM_ALIASES.get(text_key)
        if target is None and "_" in text_key:
            parts = text_key.split("_")
            target = parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])
        normalized[target or text_key] = value
    return normalized


def _normalize_dates(params: dict[str, Any]) -> None:
    for key in ("reqDate", "startDate", "endDate"):
        value = params.get(key)
        if isinstance(value, date | datetime):
            params[key] = to_yyyymmdd(value, field=key)


def _context(
    service: ServiceDefinition,
    request_url: str,
    request_params: Mapping[str, Any],
) -> ResponseContext:
    return ResponseContext(
        service_key="[redacted]",
        service_title=service.title,
        service_path=service.service_path,
        operation=service.operation,
        endpoint=service.endpoint,
        request_url=request_url,
        request_params={key: value for key, value in request_params.items() if key != "serviceKey"},
        collected_at=datetime.now(UTC),
    )


def _extract_body(payload: Mapping[str, Any], service: ServiceDefinition) -> Mapping[str, Any]:
    if "OpenAPI_ServiceResponse" in payload:
        _raise_for_openapi_service_response(payload["OpenAPI_ServiceResponse"], service)

    try:
        response = payload["response"]
        header = response["header"]
    except (KeyError, TypeError) as exc:
        raise KhoaParseError(
            "KHOA response did not contain response.header",
            endpoint=service.endpoint,
            service=service.key,
            failure_kind="parse",
        ) from exc

    if not isinstance(response, Mapping) or not isinstance(header, Mapping):
        raise KhoaParseError(
            "KHOA response/header was not an object",
            endpoint=service.endpoint,
            service=service.key,
            failure_kind="parse",
        )

    code = str(header.get("resultCode", "")).strip()
    message = str(header.get("resultMsg", "")).strip()
    body = response.get("body", {})
    if code in {"0", "00", "0000", "NORMAL_CODE", ""}:
        if not isinstance(body, Mapping):
            raise KhoaParseError(
                "KHOA response.body was not an object",
                endpoint=service.endpoint,
                service=service.key,
                failure_kind="parse",
            )
        return body
    if code == "03":
        return body if isinstance(body, Mapping) else {}
    _raise_for_result_code(code, message, service)
    raise AssertionError("unreachable")


def _extract_items(
    body: Mapping[str, Any],
    service: ServiceDefinition,
) -> tuple[Mapping[str, Any], ...]:
    items = body.get("items")
    item_data: Any
    if items in (None, "", []):
        item_data = body.get("item")
    elif isinstance(items, Mapping):
        item_data = items.get("item")
    else:
        item_data = items
    if item_data in (None, "", []):
        return ()
    if isinstance(item_data, Mapping):
        return (item_data,)
    if isinstance(item_data, list) and all(isinstance(item, Mapping) for item in item_data):
        return tuple(item_data)
    raise KhoaParseError(
        "KHOA response.body.items.item was not an object or list",
        endpoint=service.endpoint,
        service=service.key,
        failure_kind="parse",
    )


def _raise_for_openapi_service_response(data: Any, service: ServiceDefinition) -> None:
    if not isinstance(data, Mapping):
        raise KhoaParseError(
            "OpenAPI_ServiceResponse was not an object",
            endpoint=service.endpoint,
            service=service.key,
            failure_kind="parse",
        )
    header = data.get("cmmMsgHeader", data)
    if not isinstance(header, Mapping):
        raise KhoaParseError(
            "OpenAPI_ServiceResponse header was not an object",
            endpoint=service.endpoint,
            service=service.key,
            failure_kind="parse",
        )
    code = str(header.get("returnReasonCode") or "").strip()
    message = str(header.get("returnAuthMsg") or header.get("errMsg") or "KHOA service error")
    _raise_for_result_code(code, message, service)


def _raise_for_result_code(code: str, message: str, service: ServiceDefinition) -> None:
    text = f"KHOA API returned {code}: {message}" if code else message
    upper = text.upper()
    if code in {"20", "30", "31"} or "SERVICE_KEY" in upper or "AUTH" in upper:
        raise KhoaAuthError(
            text,
            endpoint=service.endpoint,
            service=service.key,
            result_code=code or None,
            failure_kind="auth",
        )
    if code == "22" or "LIMIT" in upper or "QUOTA" in upper or "TRAFFIC" in upper:
        from .exceptions import KhoaRateLimitError

        raise KhoaRateLimitError(
            text,
            endpoint=service.endpoint,
            service=service.key,
            result_code=code or None,
            failure_kind="rate_limit",
        )
    if code in {"04", "99"} or code.startswith("5"):
        from .exceptions import KhoaServerError

        raise KhoaServerError(
            text,
            endpoint=service.endpoint,
            service=service.key,
            result_code=code or None,
            failure_kind="server",
        )
    raise KhoaRequestError(
        text,
        endpoint=service.endpoint,
        service=service.key,
        result_code=code or None,
        failure_kind="request",
    )
