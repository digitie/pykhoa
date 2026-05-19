"""사용자 진입점으로 제공하는 KHOA ODMI 클라이언트."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from datetime import UTC, date, datetime
from os import PathLike
from types import TracebackType
from typing import Any, TypeVar

from ._convert import (
    csv_or_none,
    normalize_service_key,
    to_int_or_none,
    to_yyyymmdd,
    without_none,
)
from ._http import KhoaHttp, SessionLike, run_async
from .debug import DebugRun, debug_error
from .exceptions import (
    KhoaAuthError,
    KhoaNoDataError,
    KhoaParseError,
    KhoaRequestError,
    KhoaServerError,
)
from .keys import DATA_GO_KR_ENV_NAMES, get_service_key
from .models import (
    BeachIndexForecast,
    BeachIndexPlace,
    BeachSearchObservation,
    BeachSearchResult,
    MarineIndexForecast,
    MarineIndexPlace,
    Observatory,
    OceanBeachInfo,
    Page,
    RawRecord,
    ResponseContext,
    RomsPrediction,
)
from .observatories import (
    BEACH_OBSERVATORIES,
    DEFAULT_ADDRESS_SEARCH_OFFSETS_DEGREES,
    VworldReverseGeocoderLike,
    enrich_observatory_addresses,
)
from .services import (
    DEFAULT_BASE_URL,
    SERVICE_DEFINITIONS,
    ServiceDefinition,
    get_api_catalog,
    get_api_catalog_entry,
    get_service,
)

DEFAULT_ENV_NAMES = DATA_GO_KR_ENV_NAMES
KHOA_BEACH_SEARCH_URL = "https://khoa.go.kr/oceandata/api/beach/search.do"
OCEANS_BEACH_INFO_URL = (
    "http://apis.data.go.kr/1192000/service/"
    "OceansBeachInfoService1/getOceansBeachInfo1"
)
OCEANS_BEACH_INFO_ENDPOINT = "service/OceansBeachInfoService1/getOceansBeachInfo1"
OCEANS_BEACH_INFO_TITLE = "해양수산부_해수욕장정보 서비스"
OCEANS_BEACH_INFO_SERVICE_PATH = "OceansBeachInfoService1"
OCEANS_BEACH_INFO_OPERATION = "getOceansBeachInfo1"
OCEANS_BEACH_INFO_DATA_GO_KR_ID = "15058519"
OCEANS_BEACH_INFO_DEFAULT_SIDO_NAMES = (
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
)

_MARINE_INDEX_NAME_KEYS: dict[str, tuple[str, ...]] = {
    "sea_split_index": ("splocPstnNm",),
    "fishing_index": ("seafsPstnNm",),
    "seasickness_index": ("nvgtNm", "vslNm"),
    "skin_scuba_index": ("skscExpcnRgnNm",),
    "mudflat_index": ("mdftExpcnVlgNm",),
    "surfing_index": ("surfPlcNm",),
    "sea_trip_index": ("sareaDtlNm",),
}

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
        key_source: str = "data.go.kr",
        env_file: str | PathLike[str] | None = ".env",
        timeout: float = 10.0,
        retries: int = 3,
        max_rps: float = 5.0,
        session: SessionLike | None = None,
    ) -> None:
        normalized_service_key = normalize_service_key(service_key)
        normalized_api_key = normalize_service_key(api_key)
        if (
            normalized_service_key
            and normalized_api_key
            and normalized_service_key != normalized_api_key
        ):
            raise ValueError("service_key and api_key were both provided with different values")
        key = (
            normalized_api_key
            or normalized_service_key
            or get_service_key(key_source, env_file=env_file)
        )
        if not key:
            raise KhoaAuthError(
                "api_key is required. Pass api_key=... or set KHOA_SERVICE_KEY.",
                failure_kind="auth",
            )
        self.service_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.closed = False
        self._http = KhoaHttp(
            key,
            base_url=self.base_url,
            service_key_param=service_key_param,
            session=session,
            timeout=timeout,
            retries=retries,
            max_rps=max_rps,
        )

    def __enter__(self) -> KhoaClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """동기 facade에서 내부 HTTP 세션을 닫습니다."""

        self._http.close()
        self.closed = True

    async def aclose(self) -> None:
        """비동기 경로에서 내부 HTTP 세션을 닫습니다."""

        await self._http.aclose()
        self.closed = True

    @classmethod
    def aio(cls, **kwargs: Any) -> AsyncKhoaClient:
        """python-krheritage-api와 같은 형태의 async 클라이언트를 만듭니다."""

        return AsyncKhoaClient(**kwargs)

    @classmethod
    def from_env(
        cls,
        name: str = "KHOA_SERVICE_KEY",
        *,
        fallback_names: tuple[str, ...] = DEFAULT_ENV_NAMES[1:],
        env_file: str | PathLike[str] | None = ".env",
        key_source: str = "data.go.kr",
        **kwargs: Any,
    ) -> KhoaClient:
        """환경변수에서 인증키를 읽어 클라이언트를 만듭니다."""

        service_key = get_service_key(
            key_source,
            env_file=env_file,
            names=(name, *fallback_names),
        )
        if not service_key:
            names = ", ".join((name, *fallback_names))
            raise KhoaAuthError(f"none of these environment variables are set: {names}")
        return cls(api_key=service_key, **kwargs)

    @property
    def services(self) -> tuple[ServiceDefinition, ...]:
        """번들 KHOA ODMI 서비스 카탈로그를 반환합니다."""

        return SERVICE_DEFINITIONS

    def api_catalog(self) -> tuple[dict[str, Any], ...]:
        """UI 표시에 적합한 API 카탈로그 dict 목록을 반환합니다."""

        return get_api_catalog()

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

        return run_async(
            lambda: self.afetch(
                service,
                params,
                page_no=page_no,
                num_of_rows=num_of_rows,
                response_type=response_type,
                include=include,
                exclude=exclude,
                validate_required=validate_required,
                **kwargs,
            )
        )

    async def afetch(
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
        """임의 KHOA ODMI 서비스를 비동기로 호출합니다."""

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
        payload, request_url = await self._http.aget(definition, request_params)
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

    async def aitems(
        self,
        service: str | ServiceDefinition,
        **kwargs: Any,
    ) -> tuple[RawRecord, ...]:
        """서비스를 비동기로 호출하고 응답 item만 반환합니다."""

        return (await self.afetch(service, **kwargs)).items

    def debug_fetch(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> DebugRun:
        """디버그 UI/fixture 생성을 위한 fetch 실행 정보를 반환합니다."""

        return run_async(lambda: self.adebug_fetch(service, params, **kwargs))

    async def adebug_fetch(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> DebugRun:
        """디버그 UI/fixture 생성을 위한 fetch 실행 정보를 비동기로 반환합니다."""

        definition = get_service(service)
        input_data = {"service": definition.key, "params": dict(params or {}), "options": kwargs}
        catalog_entry = get_api_catalog_entry(definition)
        trace = [
            f"서비스 정의 확인: {definition.key}",
            f"데이터셋명: {catalog_entry['dataset_name']}",
            f"endpoint: {catalog_entry['endpoint']}",
            f"서비스키 신청 링크: {catalog_entry['service_key_url']}",
        ]
        try:
            page = await self.afetch(definition, params, **kwargs)
        except Exception as exc:
            trace.append(f"실행 실패: {exc.__class__.__name__}")
            return DebugRun(
                function="fetch",
                input=input_data,
                request={},
                response={},
                parsed=None,
                processed=None,
                trace=trace,
                error=debug_error(exc),
                catalog=catalog_entry,
            )

        context = page.context
        request = {
            "method": "GET",
            "url": context.request_url if context is not None else definition.endpoint,
            "query": context.request_params if context is not None else {},
            "headers": {"Accept": "application/json"},
        }
        response = {
            "status_code": 200,
            "headers": {},
            "body": page.raw,
        }
        trace.append(f"응답 item {len(page.items)}건 정규화")
        return DebugRun(
            function="fetch",
            input=input_data,
            request=request,
            response=response,
            parsed=page,
            processed=tuple(page.items),
            trace=trace,
            catalog=catalog_entry,
        )

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

    async def aiter_pages(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        max_pages: int | None = None,
        max_items: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Page[RawRecord]]:
        """선택적 안전 제한과 함께 KHOA 페이지 응답을 비동기로 순회합니다."""

        next_page = page_no
        pages = 0
        yielded = 0
        while True:
            page = await self.afetch(
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

        return run_async(
            lambda: self.aroms(
                ymin=ymin,
                ymax=ymax,
                xmin=xmin,
                xmax=xmax,
                page_no=page_no,
                num_of_rows=num_of_rows,
                include=include,
                exclude=exclude,
            )
        )

    async def aroms(
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
        """ROMS 수치예측 행을 비동기로 가져와 typed 모델로 변환합니다."""

        page = await self.afetch(
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

    def beach_index(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        response_type: str = "json",
        include: str | tuple[str, ...] | list[str] | None = None,
        exclude: str | tuple[str, ...] | list[str] | None = None,
        include_address: bool = False,
        vworld_client: VworldReverseGeocoderLike | None = None,
        vworld_api_key: str | None = None,
        vworld_domain: str | None = None,
        vworld_env_file: str | PathLike[str] | None = None,
        address_search_offsets_degrees: tuple[float, ...] = (0.0,),
        validate_required: bool = True,
        **kwargs: Any,
    ) -> Page[BeachIndexPlace]:
        """해수욕지수 행을 해수욕장별 예보 묶음 DTO로 반환합니다."""

        return run_async(
            lambda: self.abeach_index(
                params,
                page_no=page_no,
                num_of_rows=num_of_rows,
                response_type=response_type,
                include=include,
                exclude=exclude,
                include_address=include_address,
                vworld_client=vworld_client,
                vworld_api_key=vworld_api_key,
                vworld_domain=vworld_domain,
                vworld_env_file=vworld_env_file,
                address_search_offsets_degrees=address_search_offsets_degrees,
                validate_required=validate_required,
                **kwargs,
            )
        )

    async def abeach_index(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        response_type: str = "json",
        include: str | tuple[str, ...] | list[str] | None = None,
        exclude: str | tuple[str, ...] | list[str] | None = None,
        include_address: bool = False,
        vworld_client: VworldReverseGeocoderLike | None = None,
        vworld_api_key: str | None = None,
        vworld_domain: str | None = None,
        vworld_env_file: str | PathLike[str] | None = None,
        address_search_offsets_degrees: tuple[float, ...] = (0.0,),
        validate_required: bool = True,
        **kwargs: Any,
    ) -> Page[BeachIndexPlace]:
        """해수욕지수 행을 비동기로 가져와 해수욕장별 예보 묶음 DTO로 반환합니다."""

        page = await self.afetch(
            "beach_index",
            params,
            page_no=page_no,
            num_of_rows=num_of_rows,
            response_type=response_type,
            include=include,
            exclude=exclude,
            validate_required=validate_required,
            **kwargs,
        )
        return _beach_index_place_page(
            page,
            include_address=include_address,
            vworld_client=vworld_client,
            vworld_api_key=vworld_api_key,
            vworld_domain=vworld_domain,
            vworld_env_file=vworld_env_file,
            search_offsets_degrees=address_search_offsets_degrees,
        )

    def beach_search(
        self,
        beach_code: str,
        *,
        service_key: str | None = None,
        env_file: str | PathLike[str] | None = ".env",
        include_address: bool = True,
    ) -> BeachSearchResult:
        """KHOA `beach/search.do`에서 해수욕장 최신 관측 정보를 가져옵니다."""

        return run_async(
            lambda: self.abeach_search(
                beach_code,
                service_key=service_key,
                env_file=env_file,
                include_address=include_address,
            )
        )

    async def abeach_search(
        self,
        beach_code: str,
        *,
        service_key: str | None = None,
        env_file: str | PathLike[str] | None = ".env",
        include_address: bool = True,
    ) -> BeachSearchResult:
        """KHOA `beach/search.do`에서 해수욕장 최신 관측 정보를 비동기로 가져옵니다."""

        key = normalize_service_key(service_key) or get_service_key(
            "khoa.go.kr",
            env_file=env_file,
        ) or self.service_key
        params = {"ServiceKey": key, "BeachCode": beach_code}
        payload, _request_url = await self._http.aget_url(
            KHOA_BEACH_SEARCH_URL,
            params=params,
            endpoint="beach/search.do",
            service_key=key,
        )
        return _beach_search_result(payload, include_address=include_address)

    def oceans_beach_info(
        self,
        sido_nm: str,
        *,
        page_no: int = 1,
        num_of_rows: int = 100,
        response_type: str = "JSON",
        service_key: str | None = None,
    ) -> Page[OceanBeachInfo]:
        """공공데이터포털 해양수산부 해수욕장정보 한 페이지를 반환합니다."""

        return run_async(
            lambda: self.aoceans_beach_info(
                sido_nm,
                page_no=page_no,
                num_of_rows=num_of_rows,
                response_type=response_type,
                service_key=service_key,
            )
        )

    async def aoceans_beach_info(
        self,
        sido_nm: str,
        *,
        page_no: int = 1,
        num_of_rows: int = 100,
        response_type: str = "JSON",
        service_key: str | None = None,
    ) -> Page[OceanBeachInfo]:
        """공공데이터포털 해양수산부 해수욕장정보 한 페이지를 비동기로 반환합니다."""

        if page_no < 1:
            raise ValueError("page_no must be >= 1")
        if not 1 <= num_of_rows <= 1000:
            raise ValueError("num_of_rows must be between 1 and 1000")
        sido_name = sido_nm.strip()
        if not sido_name:
            raise KhoaRequestError(
                "oceans_beach_info requires SIDO_NM",
                provider="data.go.kr",
                endpoint=OCEANS_BEACH_INFO_ENDPOINT,
                failure_kind="request",
            )

        key = normalize_service_key(service_key) or self.service_key
        params: dict[str, Any] = {
            "ServiceKey": key,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "SIDO_NM": sido_name,
            "resultType": response_type,
        }
        payload, _request_url = await self._http.aget_url(
            OCEANS_BEACH_INFO_URL,
            params=without_none(params),
            endpoint=OCEANS_BEACH_INFO_ENDPOINT,
            service_key=key,
        )

        body = _extract_data_go_body(
            payload,
            provider="data.go.kr",
            endpoint=OCEANS_BEACH_INFO_ENDPOINT,
        )
        rows = _extract_direct_items(
            body,
            provider="data.go.kr",
            endpoint=OCEANS_BEACH_INFO_ENDPOINT,
        )
        request_params = {
            key: value for key, value in params.items() if key != "ServiceKey"
        }
        return Page[OceanBeachInfo](
            items=tuple(OceanBeachInfo.from_raw(row) for row in rows),
            total_count=to_int_or_none(body.get("totalCount")) or len(rows),
            page_no=to_int_or_none(body.get("pageNo")) or page_no,
            num_of_rows=to_int_or_none(body.get("numOfRows")) or num_of_rows,
            raw=dict(body),
            context=ResponseContext(
                provider="data.go.kr",
                service_key="[redacted]",
                service_title=OCEANS_BEACH_INFO_TITLE,
                service_path=OCEANS_BEACH_INFO_SERVICE_PATH,
                operation=OCEANS_BEACH_INFO_OPERATION,
                endpoint=OCEANS_BEACH_INFO_ENDPOINT,
                request_url=OCEANS_BEACH_INFO_URL,
                request_params=request_params,
                collected_at=datetime.now(UTC),
            ),
        )

    def iter_oceans_beach_info_pages(
        self,
        *,
        sido_names: tuple[str, ...] | list[str] | None = None,
        page_no: int = 1,
        num_of_rows: int = 100,
        max_pages: int | None = None,
        max_items: int | None = None,
        response_type: str = "JSON",
        service_key: str | None = None,
    ) -> Iterator[Page[OceanBeachInfo]]:
        """시도명 목록을 순회하며 해수욕장정보 페이지를 모두 반환합니다."""

        names = tuple(sido_names or OCEANS_BEACH_INFO_DEFAULT_SIDO_NAMES)
        yielded_pages = 0
        yielded_items = 0
        for sido_name in names:
            next_page = page_no
            while True:
                page = self.oceans_beach_info(
                    sido_name,
                    page_no=next_page,
                    num_of_rows=num_of_rows,
                    response_type=response_type,
                    service_key=service_key,
                )
                if page.items:
                    yield page
                    yielded_pages += 1
                    yielded_items += len(page.items)
                if max_pages is not None and yielded_pages >= max_pages:
                    return
                if max_items is not None and yielded_items >= max_items:
                    return
                if not page.items or page.next_page_no is None:
                    break
                next_page = page.next_page_no

    async def aiter_oceans_beach_info_pages(
        self,
        *,
        sido_names: tuple[str, ...] | list[str] | None = None,
        page_no: int = 1,
        num_of_rows: int = 100,
        max_pages: int | None = None,
        max_items: int | None = None,
        response_type: str = "JSON",
        service_key: str | None = None,
    ) -> AsyncIterator[Page[OceanBeachInfo]]:
        """시도명 목록을 순회하며 해수욕장정보 페이지를 비동기로 반환합니다."""

        names = tuple(sido_names or OCEANS_BEACH_INFO_DEFAULT_SIDO_NAMES)
        yielded_pages = 0
        yielded_items = 0
        for sido_name in names:
            next_page = page_no
            while True:
                page = await self.aoceans_beach_info(
                    sido_name,
                    page_no=next_page,
                    num_of_rows=num_of_rows,
                    response_type=response_type,
                    service_key=service_key,
                )
                if page.items:
                    yield page
                    yielded_pages += 1
                    yielded_items += len(page.items)
                if max_pages is not None and yielded_pages >= max_pages:
                    return
                if max_items is not None and yielded_items >= max_items:
                    return
                if not page.items or page.next_page_no is None:
                    break
                next_page = page.next_page_no

    def sea_split_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """바다갈라짐 체험지수를 장소별 DTO로 반환합니다."""

        return self._marine_index("sea_split_index", **kwargs)

    async def asea_split_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """바다갈라짐 체험지수를 장소별 DTO로 비동기 반환합니다."""

        return await self._amarine_index("sea_split_index", **kwargs)

    def fishing_index(self, *, gubun: str, **kwargs: Any) -> Page[MarineIndexPlace]:
        """바다낚시지수를 장소별 DTO로 반환합니다."""

        return self._marine_index("fishing_index", gubun=gubun, **kwargs)

    async def afishing_index(self, *, gubun: str, **kwargs: Any) -> Page[MarineIndexPlace]:
        """바다낚시지수를 장소별 DTO로 비동기 반환합니다."""

        return await self._amarine_index("fishing_index", gubun=gubun, **kwargs)

    def seasickness_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """뱃멀미지수를 항로/선박별 DTO로 반환합니다."""

        return self._marine_index("seasickness_index", **kwargs)

    async def aseasickness_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """뱃멀미지수를 항로/선박별 DTO로 비동기 반환합니다."""

        return await self._amarine_index("seasickness_index", **kwargs)

    def skin_scuba_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """스킨스쿠버지수를 장소별 DTO로 반환합니다."""

        return self._marine_index("skin_scuba_index", **kwargs)

    async def askin_scuba_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """스킨스쿠버지수를 장소별 DTO로 비동기 반환합니다."""

        return await self._amarine_index("skin_scuba_index", **kwargs)

    def mudflat_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """갯벌체험지수를 장소별 DTO로 반환합니다."""

        return self._marine_index("mudflat_index", **kwargs)

    async def amudflat_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """갯벌체험지수를 장소별 DTO로 비동기 반환합니다."""

        return await self._amarine_index("mudflat_index", **kwargs)

    def surfing_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """서핑지수를 장소별 DTO로 반환합니다."""

        return self._marine_index("surfing_index", **kwargs)

    async def asurfing_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """서핑지수를 장소별 DTO로 비동기 반환합니다."""

        return await self._amarine_index("surfing_index", **kwargs)

    def sea_trip_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """바다여행지수를 장소별 DTO로 반환합니다."""

        return self._marine_index("sea_trip_index", **kwargs)

    async def asea_trip_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        """바다여행지수를 장소별 DTO로 비동기 반환합니다."""

        return await self._amarine_index("sea_trip_index", **kwargs)

    def _marine_index(
        self,
        service: str,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        response_type: str = "json",
        include: str | tuple[str, ...] | list[str] | None = None,
        exclude: str | tuple[str, ...] | list[str] | None = None,
        include_address: bool = False,
        vworld_client: VworldReverseGeocoderLike | None = None,
        vworld_api_key: str | None = None,
        vworld_domain: str | None = None,
        vworld_env_file: str | PathLike[str] | None = None,
        address_search_offsets_degrees: tuple[
            float, ...
        ] = DEFAULT_ADDRESS_SEARCH_OFFSETS_DEGREES,
        validate_required: bool = True,
        **kwargs: Any,
    ) -> Page[MarineIndexPlace]:
        page = self.fetch(
            service,
            params,
            page_no=page_no,
            num_of_rows=num_of_rows,
            response_type=response_type,
            include=include,
            exclude=exclude,
            validate_required=validate_required,
            **kwargs,
        )
        return _marine_index_place_page(
            page,
            service_key=service,
            name_keys=_MARINE_INDEX_NAME_KEYS[service],
            include_address=include_address,
            vworld_client=vworld_client,
            vworld_api_key=vworld_api_key,
            vworld_domain=vworld_domain,
            vworld_env_file=vworld_env_file,
            search_offsets_degrees=address_search_offsets_degrees,
        )

    async def _amarine_index(
        self,
        service: str,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        response_type: str = "json",
        include: str | tuple[str, ...] | list[str] | None = None,
        exclude: str | tuple[str, ...] | list[str] | None = None,
        include_address: bool = False,
        vworld_client: VworldReverseGeocoderLike | None = None,
        vworld_api_key: str | None = None,
        vworld_domain: str | None = None,
        vworld_env_file: str | PathLike[str] | None = None,
        address_search_offsets_degrees: tuple[
            float, ...
        ] = DEFAULT_ADDRESS_SEARCH_OFFSETS_DEGREES,
        validate_required: bool = True,
        **kwargs: Any,
    ) -> Page[MarineIndexPlace]:
        page = await self.afetch(
            service,
            params,
            page_no=page_no,
            num_of_rows=num_of_rows,
            response_type=response_type,
            include=include,
            exclude=exclude,
            validate_required=validate_required,
            **kwargs,
        )
        return _marine_index_place_page(
            page,
            service_key=service,
            name_keys=_MARINE_INDEX_NAME_KEYS[service],
            include_address=include_address,
            vworld_client=vworld_client,
            vworld_api_key=vworld_api_key,
            vworld_domain=vworld_domain,
            vworld_env_file=vworld_env_file,
            search_offsets_degrees=address_search_offsets_degrees,
        )

    def first(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> RawRecord:
        """첫 번째 원문 item을 반환하거나 KhoaNoDataError를 발생시킵니다."""

        return run_async(lambda: self.afirst(service, params, **kwargs))

    async def afirst(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> RawRecord:
        """첫 번째 원문 item을 비동기로 반환하거나 KhoaNoDataError를 발생시킵니다."""

        page = await self.afetch(service, params, **kwargs)
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


class AsyncKhoaClient:
    """python-krheritage-api와 같은 형태의 비동기 KHOA facade."""

    def __init__(self, **kwargs: Any) -> None:
        self._client = KhoaClient(**kwargs)

    async def __aenter__(self) -> AsyncKhoaClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    @classmethod
    def from_env(cls, **kwargs: Any) -> AsyncKhoaClient:
        """환경변수에서 인증키를 읽어 비동기 클라이언트를 만듭니다."""

        client = KhoaClient.from_env(**kwargs)
        async_client = cls.__new__(cls)
        async_client._client = client
        return async_client

    @property
    def service_key(self) -> str:
        return self._client.service_key

    @property
    def base_url(self) -> str:
        return self._client.base_url

    @property
    def timeout(self) -> float:
        return self._client.timeout

    @property
    def closed(self) -> bool:
        return self._client.closed

    @property
    def services(self) -> tuple[ServiceDefinition, ...]:
        return self._client.services

    def api_catalog(self) -> tuple[dict[str, Any], ...]:
        return self._client.api_catalog()

    def service(self, key: str | ServiceDefinition) -> ServiceDefinition:
        return self._client.service(key)

    async def aclose(self) -> None:
        await self._client.aclose()

    def __getattr__(self, name: str) -> Callable[..., Any]:
        try:
            service = get_service(name)
        except KeyError as exc:
            raise AttributeError(name) from exc

        async def caller(**kwargs: Any) -> Page[RawRecord]:
            return await self.fetch(service, **kwargs)

        return caller

    async def fetch(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Page[RawRecord]:
        return await self._client.afetch(service, params, **kwargs)

    async def items(
        self,
        service: str | ServiceDefinition,
        **kwargs: Any,
    ) -> tuple[RawRecord, ...]:
        return await self._client.aitems(service, **kwargs)

    async def debug_fetch(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> DebugRun:
        return await self._client.adebug_fetch(service, params, **kwargs)

    def iter_pages(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Page[RawRecord]]:
        return self._client.aiter_pages(service, params, **kwargs)

    async def roms(self, **kwargs: Any) -> Page[RomsPrediction]:
        return await self._client.aroms(**kwargs)

    async def beach_index(
        self,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Page[BeachIndexPlace]:
        return await self._client.abeach_index(params, **kwargs)

    async def beach_search(self, beach_code: str, **kwargs: Any) -> BeachSearchResult:
        return await self._client.abeach_search(beach_code, **kwargs)

    async def oceans_beach_info(self, sido_nm: str, **kwargs: Any) -> Page[OceanBeachInfo]:
        return await self._client.aoceans_beach_info(sido_nm, **kwargs)

    def iter_oceans_beach_info_pages(
        self,
        **kwargs: Any,
    ) -> AsyncIterator[Page[OceanBeachInfo]]:
        return self._client.aiter_oceans_beach_info_pages(**kwargs)

    async def sea_split_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        return await self._client.asea_split_index(**kwargs)

    async def fishing_index(self, *, gubun: str, **kwargs: Any) -> Page[MarineIndexPlace]:
        return await self._client.afishing_index(gubun=gubun, **kwargs)

    async def seasickness_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        return await self._client.aseasickness_index(**kwargs)

    async def skin_scuba_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        return await self._client.askin_scuba_index(**kwargs)

    async def mudflat_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        return await self._client.amudflat_index(**kwargs)

    async def surfing_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        return await self._client.asurfing_index(**kwargs)

    async def sea_trip_index(self, **kwargs: Any) -> Page[MarineIndexPlace]:
        return await self._client.asea_trip_index(**kwargs)

    async def first(
        self,
        service: str | ServiceDefinition,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> RawRecord:
        return await self._client.afirst(service, params, **kwargs)


KhoaODMIClient = KhoaClient


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

    response = payload.get("response")
    if isinstance(response, Mapping):
        header = response.get("header")
        body = response.get("body", {})
    else:
        header = payload.get("header")
        body = payload.get("body", {})

    if header is None:
        raise KhoaParseError(
            "KHOA response did not contain response.header",
            endpoint=service.endpoint,
            service=service.key,
            failure_kind="parse",
        )

    if not isinstance(response, Mapping) or not isinstance(header, Mapping):
        if response is not None or not isinstance(header, Mapping):
            raise KhoaParseError(
                "KHOA response/header was not an object",
                endpoint=service.endpoint,
                service=service.key,
                failure_kind="parse",
            )

    code = str(header.get("resultCode", "")).strip()
    message = str(header.get("resultMsg", "")).strip()
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


def _beach_index_place_page(
    page: Page[RawRecord],
    *,
    include_address: bool,
    vworld_client: VworldReverseGeocoderLike | None,
    vworld_api_key: str | None,
    vworld_domain: str | None,
    vworld_env_file: str | PathLike[str] | None,
    search_offsets_degrees: tuple[float, ...],
) -> Page[BeachIndexPlace]:
    groups: dict[tuple[str, str, float, float], list[RawRecord]] = {}
    observatories: dict[tuple[str, str, float, float], Observatory] = {}
    for row in page.items:
        observatory = _beach_index_observatory(row)
        if observatory is None:
            continue
        key = _beach_index_place_key(observatory)
        groups.setdefault(key, []).append(row)
        observatories.setdefault(key, observatory)

    if include_address and observatories:
        observatories = _beach_index_address_observatories(
            observatories,
            vworld_client=vworld_client,
            vworld_api_key=vworld_api_key,
            vworld_domain=vworld_domain,
            vworld_env_file=vworld_env_file,
            search_offsets_degrees=search_offsets_degrees,
        )

    items = tuple(
        _beach_index_place_from_rows(observatories[key], rows)
        for key, rows in groups.items()
    )

    return Page[BeachIndexPlace](
        items=items,
        total_count=page.total_count,
        page_no=page.page_no,
        num_of_rows=page.num_of_rows,
        raw=page.raw,
        context=page.context,
    )


def _beach_index_observatory(row: Mapping[str, Any]) -> Observatory | None:
    name = _row_text(row, "bbchNm", "beachName", "placeName")
    latitude = _row_float(row, "lat", "latitude")
    longitude = _row_float(row, "lot", "lon", "longitude")
    if name is None or latitude is None or longitude is None:
        return None

    matched = _find_beach_observatory(name, latitude, longitude)
    beach_code = _row_text(row, "placeCode", "beachCode", "obsvtrId")
    return Observatory.from_raw(
        {
            **dict(row),
            "id": beach_code or (matched.id if matched is not None else name),
            "name": name,
            "data_type": "BEACH",
            "lat": latitude,
            "lon": longitude,
        }
    )


def _beach_index_place_key(observatory: Observatory) -> tuple[str, str, float, float]:
    return (
        observatory.id,
        observatory.name,
        round(observatory.lat, 6),
        round(observatory.lon, 6),
    )


def _beach_index_address_observatories(
    observatories: dict[tuple[str, str, float, float], Observatory],
    *,
    vworld_client: VworldReverseGeocoderLike | None,
    vworld_api_key: str | None,
    vworld_domain: str | None,
    vworld_env_file: str | PathLike[str] | None,
    search_offsets_degrees: tuple[float, ...],
) -> dict[tuple[str, str, float, float], Observatory]:
    if not _has_live_vworld_options(
        vworld_client=vworld_client,
        vworld_api_key=vworld_api_key,
        vworld_domain=vworld_domain,
        vworld_env_file=vworld_env_file,
    ):
        return {
            key: _cached_beach_index_address_observatory(observatory)
            for key, observatory in observatories.items()
        }

    lookup_observatories = tuple(
        _beach_index_lookup_observatory(observatory)
        for observatory in observatories.values()
    )
    enriched_values = enrich_observatory_addresses(
        lookup_observatories,
        vworld_client=vworld_client,
        vworld_api_key=vworld_api_key,
        vworld_domain=vworld_domain,
        vworld_env_file=vworld_env_file,
        search_offsets_degrees=search_offsets_degrees,
    )
    return {
        key: _merge_beach_index_address(original, enriched)
        for (key, original), enriched in zip(
            observatories.items(),
            enriched_values,
            strict=True,
        )
    }


def _has_live_vworld_options(
    *,
    vworld_client: VworldReverseGeocoderLike | None,
    vworld_api_key: str | None,
    vworld_domain: str | None,
    vworld_env_file: str | PathLike[str] | None,
) -> bool:
    return any(
        value is not None
        for value in (vworld_client, vworld_api_key, vworld_domain, vworld_env_file)
    )


def _cached_beach_index_address_observatory(observatory: Observatory) -> Observatory:
    cached = _find_beach_observatory(observatory.name, observatory.lat, observatory.lon)
    if cached is None:
        return observatory
    return _merge_beach_index_address(observatory, cached)


def _beach_index_lookup_observatory(observatory: Observatory) -> Observatory:
    cached = _find_beach_observatory(observatory.name, observatory.lat, observatory.lon)
    lookup_coordinate = (
        cached.address_coordinate
        if cached is not None and cached.address_coordinate is not None
        else observatory.coordinate
    )
    return observatory.model_copy(
        update={
            "coordinate": lookup_coordinate,
            "address": None,
            "address_coordinate": None,
            "address_distance_m": None,
            "address_match_type": None,
            "address_source": None,
        }
    )


def _merge_beach_index_address(
    original: Observatory,
    enriched: Observatory,
) -> Observatory:
    address_coordinate = enriched.address_coordinate
    distance = (
        original.coordinate.distance_to_m(address_coordinate)
        if address_coordinate is not None
        else None
    )
    match_type = (
        "exact"
        if distance == 0
        else "nearby"
        if distance is not None
        else enriched.address_match_type
    )
    return original.model_copy(
        update={
            "address": enriched.address,
            "address_coordinate": address_coordinate,
            "address_distance_m": round(distance, 3) if distance is not None else None,
            "address_match_type": match_type,
            "address_source": enriched.address_source,
        }
    )


def _beach_index_place_from_rows(
    observatory: Observatory,
    rows: list[RawRecord],
) -> BeachIndexPlace:
    return BeachIndexPlace(
        id=observatory.id,
        name=observatory.name,
        coordinate=observatory.coordinate,
        forecasts=tuple(BeachIndexForecast.from_raw(row) for row in rows),
        address=observatory.address,
        address_coordinate=observatory.address_coordinate,
        address_distance_m=observatory.address_distance_m,
        address_match_type=observatory.address_match_type,
        address_source=observatory.address_source,
        raw={"rows": [dict(row) for row in rows]},
    )


def _extract_data_go_body(
    payload: Mapping[str, Any],
    *,
    provider: str,
    endpoint: str,
) -> Mapping[str, Any]:
    if "OpenAPI_ServiceResponse" in payload:
        _raise_direct_openapi_service_response(
            payload["OpenAPI_ServiceResponse"],
            provider=provider,
            endpoint=endpoint,
        )

    payload = _unwrap_direct_payload(payload)
    response = payload.get("response")
    if isinstance(response, Mapping):
        header = response.get("header")
        body = response.get("body", {})
    else:
        header = payload.get("header")
        body = payload.get("body")
        if body is None:
            body = {key: value for key, value in payload.items() if key != "header"}
    if not isinstance(header, Mapping):
        raise KhoaParseError(
            "data.go.kr response did not contain response.header",
            provider=provider,
            endpoint=endpoint,
            failure_kind="parse",
        )

    code = str(header.get("resultCode", header.get("code", ""))).strip()
    message = str(header.get("resultMsg", header.get("message", ""))).strip()
    if code in {"0", "00", "0000", "NORMAL_CODE", ""}:
        if not isinstance(body, Mapping):
            raise KhoaParseError(
                "data.go.kr response.body was not an object",
                provider=provider,
                endpoint=endpoint,
                failure_kind="parse",
            )
        return body
    if code == "03":
        return body if isinstance(body, Mapping) else {}
    _raise_direct_result_code(code, message, provider=provider, endpoint=endpoint)
    raise AssertionError("unreachable")


def _unwrap_direct_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if "response" in payload or "header" in payload or "body" in payload:
        return payload
    for value in payload.values():
        if isinstance(value, Mapping) and "header" in value:
            return value
    return payload


def _extract_direct_items(
    body: Mapping[str, Any],
    *,
    provider: str,
    endpoint: str,
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
        "data.go.kr response.body.items.item was not an object or list",
        provider=provider,
        endpoint=endpoint,
        failure_kind="parse",
    )


def _raise_direct_openapi_service_response(
    data: Any,
    *,
    provider: str,
    endpoint: str,
) -> None:
    if not isinstance(data, Mapping):
        raise KhoaParseError(
            "OpenAPI_ServiceResponse was not an object",
            provider=provider,
            endpoint=endpoint,
            failure_kind="parse",
        )
    header = data.get("cmmMsgHeader", data)
    if not isinstance(header, Mapping):
        raise KhoaParseError(
            "OpenAPI_ServiceResponse header was not an object",
            provider=provider,
            endpoint=endpoint,
            failure_kind="parse",
        )
    code = str(header.get("returnReasonCode") or "").strip()
    message = str(header.get("returnAuthMsg") or header.get("errMsg") or "data.go.kr error")
    _raise_direct_result_code(code, message, provider=provider, endpoint=endpoint)


def _raise_direct_result_code(
    code: str,
    message: str,
    *,
    provider: str,
    endpoint: str,
) -> None:
    text = f"data.go.kr API returned {code}: {message}" if code else message
    upper = text.upper()
    if code in {"20", "30", "31"} or "SERVICE_KEY" in upper or "AUTH" in upper:
        raise KhoaAuthError(
            text,
            provider=provider,
            endpoint=endpoint,
            result_code=code or None,
            failure_kind="auth",
        )
    if code == "22" or "LIMIT" in upper or "QUOTA" in upper or "TRAFFIC" in upper:
        from .exceptions import KhoaRateLimitError

        raise KhoaRateLimitError(
            text,
            provider=provider,
            endpoint=endpoint,
            result_code=code or None,
            failure_kind="rate_limit",
        )
    if code in {"04", "99"} or code.startswith("5"):
        raise KhoaServerError(
            text,
            provider=provider,
            endpoint=endpoint,
            result_code=code or None,
            failure_kind="server",
        )
    raise KhoaRequestError(
        text,
        provider=provider,
        endpoint=endpoint,
        result_code=code or None,
        failure_kind="request",
    )


def _raise_direct_status(
    status_code: int,
    text: str,
    *,
    endpoint: str,
    key: str,
    provider: str = "khoa.go.kr",
) -> None:
    if status_code < 400:
        return

    message = _redact_secret(text.strip() or f"direct endpoint returned {status_code}", key)
    if status_code in {401, 403}:
        raise KhoaAuthError(
            message,
            provider=provider,
            endpoint=endpoint,
            status_code=status_code,
            failure_kind="auth",
        )
    if status_code == 429:
        from .exceptions import KhoaRateLimitError

        raise KhoaRateLimitError(
            message,
            provider=provider,
            endpoint=endpoint,
            status_code=status_code,
            failure_kind="rate_limit",
        )
    if status_code >= 500:
        raise KhoaServerError(
            message,
            provider=provider,
            endpoint=endpoint,
            status_code=status_code,
            failure_kind="server",
            retryable=True,
        )
    raise KhoaRequestError(
        message,
        provider=provider,
        endpoint=endpoint,
        status_code=status_code,
        failure_kind="request",
    )


def _redact_secret(text: str, key: str) -> str:
    return text.replace(key, "[redacted]") if key else text


def _beach_search_result(
    payload: Mapping[str, Any],
    *,
    include_address: bool,
) -> BeachSearchResult:
    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise KhoaParseError(
            "KHOA beach search response did not contain result object",
            provider="khoa.go.kr",
            endpoint="beach/search.do",
            failure_kind="parse",
        )

    error = _row_text(result, "error")
    if error is not None:
        _raise_direct_payload_error(error, endpoint="beach/search.do")

    meta_value = result.get("meta")
    meta: Mapping[str, Any] = meta_value if isinstance(meta_value, Mapping) else {}
    rows = _direct_mapping_rows(result.get("data"), endpoint="beach/search.do")

    beach_code = _row_text(meta, "beach_code", "beachCode", "BeachCode")
    obs_post_name = _row_text(meta, "obs_post_name", "obsPostName")
    beach_name = _row_text(meta, "beach_name", "beachName") or obs_post_name
    if beach_code is None:
        raise KhoaParseError(
            "KHOA beach search response did not contain meta.beach_code",
            provider="khoa.go.kr",
            endpoint="beach/search.do",
            failure_kind="parse",
        )

    observatory = _find_beach_observatory_by_id_or_name(beach_code, beach_name)
    address = observatory.address if include_address and observatory is not None else None
    address_coordinate = (
        observatory.address_coordinate if include_address and observatory is not None else None
    )
    return BeachSearchResult(
        id=beach_code,
        name=beach_name or beach_code,
        obs_post_name=obs_post_name,
        coordinate=observatory.coordinate if observatory is not None else None,
        observations=tuple(BeachSearchObservation.from_raw(row) for row in rows),
        address=address,
        address_coordinate=address_coordinate,
        address_distance_m=observatory.address_distance_m
        if include_address and observatory is not None
        else None,
        address_match_type=observatory.address_match_type
        if include_address and observatory is not None
        else None,
        address_source=observatory.address_source
        if include_address and observatory is not None
        else None,
        raw=dict(payload),
    )


def _raise_direct_payload_error(message: str, *, endpoint: str) -> None:
    normalized = message.replace("_", "").replace(" ", "").lower()
    if "servicekey" in normalized or "auth" in normalized:
        raise KhoaAuthError(
            message,
            provider="khoa.go.kr",
            endpoint=endpoint,
            failure_kind="auth",
        )
    raise KhoaRequestError(
        message,
        provider="khoa.go.kr",
        endpoint=endpoint,
        failure_kind="request",
    )


def _direct_mapping_rows(value: Any, *, endpoint: str) -> tuple[Mapping[str, Any], ...]:
    if value in (None, "", []):
        return ()
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list) and all(isinstance(row, Mapping) for row in value):
        return tuple(value)
    raise KhoaParseError(
        "KHOA direct response data was not an object or list",
        provider="khoa.go.kr",
        endpoint=endpoint,
        failure_kind="parse",
    )


def _marine_index_place_page(
    page: Page[RawRecord],
    *,
    service_key: str,
    name_keys: tuple[str, ...],
    include_address: bool,
    vworld_client: VworldReverseGeocoderLike | None,
    vworld_api_key: str | None,
    vworld_domain: str | None,
    vworld_env_file: str | PathLike[str] | None,
    search_offsets_degrees: tuple[float, ...],
) -> Page[MarineIndexPlace]:
    groups: dict[tuple[str, str, str, float, float], list[RawRecord]] = {}
    observatories: dict[tuple[str, str, str, float, float], Observatory] = {}

    for row in page.items:
        observatory = _marine_index_observatory(row, service_key, name_keys=name_keys)
        if observatory is None:
            continue
        key = _marine_index_place_key(service_key, observatory)
        groups.setdefault(key, []).append(row)
        observatories.setdefault(key, observatory)

    if include_address and observatories:
        enriched_values = enrich_observatory_addresses(
            tuple(observatories.values()),
            vworld_client=vworld_client,
            vworld_api_key=vworld_api_key,
            vworld_domain=vworld_domain,
            vworld_env_file=vworld_env_file,
            search_offsets_degrees=search_offsets_degrees,
            require_road_address=False,
        )
        observatories = {
            key: _merge_marine_index_address(original, enriched)
            for (key, original), enriched in zip(
                observatories.items(),
                enriched_values,
                strict=True,
            )
        }

    items = tuple(
        _marine_index_place_from_rows(
            service_key,
            name_keys,
            observatories[key],
            rows,
        )
        for key, rows in groups.items()
    )

    return Page[MarineIndexPlace](
        items=items,
        total_count=page.total_count,
        page_no=page.page_no,
        num_of_rows=page.num_of_rows,
        raw=page.raw,
        context=page.context,
    )


def _marine_index_observatory(
    row: Mapping[str, Any],
    service_key: str,
    *,
    name_keys: tuple[str, ...],
) -> Observatory | None:
    name = _row_text(row, *name_keys)
    latitude = _row_float(row, "lat", "latitude")
    longitude = _row_float(row, "lot", "lon", "longitude")
    if name is None or latitude is None or longitude is None:
        return None

    place_id = _row_text(
        row,
        "placeCode",
        "place_code",
        "nvgtCode",
        "vnpCode",
        "obsCode",
        "predcMdlId",
    )
    place_id = place_id or f"{service_key}:{name}:{latitude:.6f}:{longitude:.6f}"
    return Observatory.from_raw(
        {
            **dict(row),
            "id": place_id,
            "name": name,
            "data_type": service_key,
            "lat": latitude,
            "lon": longitude,
        }
    )


def _marine_index_place_key(
    service_key: str,
    observatory: Observatory,
) -> tuple[str, str, str, float, float]:
    return (
        service_key,
        observatory.id,
        observatory.name,
        round(observatory.lat, 6),
        round(observatory.lon, 6),
    )


def _merge_marine_index_address(original: Observatory, enriched: Observatory) -> Observatory:
    address_coordinate = enriched.address_coordinate
    distance = (
        original.coordinate.distance_to_m(address_coordinate)
        if address_coordinate is not None
        else None
    )
    return original.model_copy(
        update={
            "address": enriched.address,
            "address_coordinate": address_coordinate,
            "address_distance_m": round(distance, 3) if distance is not None else None,
            "address_match_type": enriched.address_match_type,
            "address_source": enriched.address_source,
        }
    )


def _marine_index_place_from_rows(
    service_key: str,
    name_keys: tuple[str, ...],
    observatory: Observatory,
    rows: list[RawRecord],
) -> MarineIndexPlace:
    return MarineIndexPlace(
        service_key=service_key,
        id=observatory.id,
        name=observatory.name,
        coordinate=observatory.coordinate,
        forecasts=tuple(
            MarineIndexForecast.from_raw(row, excluded_keys=name_keys)
            for row in rows
        ),
        address=observatory.address,
        address_coordinate=observatory.address_coordinate,
        address_distance_m=observatory.address_distance_m,
        address_match_type=observatory.address_match_type,
        address_source=observatory.address_source,
        raw={"rows": [dict(row) for row in rows]},
    )


def _find_beach_observatory_by_id_or_name(
    beach_code: str,
    name: str | None,
) -> Observatory | None:
    for observatory in BEACH_OBSERVATORIES:
        if observatory.id == beach_code:
            return observatory

    if name is None:
        return None
    same_name = [observatory for observatory in BEACH_OBSERVATORIES if observatory.name == name]
    if len(same_name) == 1:
        return same_name[0]
    return None


def _find_beach_observatory(name: str, latitude: float, longitude: float) -> Observatory | None:
    for observatory in BEACH_OBSERVATORIES:
        if (
            observatory.name == name
            and abs(observatory.lat - latitude) < 0.0005
            and abs(observatory.lon - longitude) < 0.0005
        ):
            return observatory

    same_name = [observatory for observatory in BEACH_OBSERVATORIES if observatory.name == name]
    if len(same_name) == 1:
        return same_name[0]
    return None


def _row_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _row_float(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
