"""KHOA 포털 관측소 목록과 해수욕장 번들 데이터.

KHOA ODMI 서비스는 보통 data.go.kr 엔드포인트로 제공되지만, 포털 상세
페이지의 관측소 목록은 별도 AJAX 엔드포인트에 들어 있습니다. 이 모듈은 그
비표준 엔드포인트를 감싸고, "해수욕장 정보" 상세 페이지의 관측소 목록을
번들 데이터로 제공합니다.
"""

from __future__ import annotations

import base64
import importlib
import json
import math
import zlib
from collections.abc import Mapping
from os import PathLike
from typing import Any, Final, Protocol, cast

import requests

from .exceptions import KhoaParseError, KhoaRequestError, KhoaServerError
from .models import Observatory

KHOA_OPENAPI_INFO_URL: Final = "https://www.khoa.go.kr/oceandata/openapi/getOpenApiInfo.do"
KHOA_OPENAPI_DETAIL_URL: Final = "https://www.khoa.go.kr/oceandata/openapi/openApiDetail.do"

BEACH_OPENAPI_ID: Final = "36"
BEACH_INFO_TITLE: Final = "해수욕장 정보"
BEACH_INFO_MODIFY_CYCLE: Final = "상시"
BEACH_INFO_UPDATE_INTERVAL_MINUTES: Final = 30
BEACH_OBSERVATORY_SOURCE_DATE: Final = "2026-05-10"
BEACH_OBSERVATORY_SOURCE_SHA256: Final = (
    "9e66998c51c367388e756cf2c1af464a6318c451fdccb706435730e8cd2e653a"
)
DEFAULT_ADDRESS_SEARCH_OFFSETS_DEGREES: Final = (
    0.0,
    0.0005,
    0.001,
    0.002,
    0.003,
    0.005,
    0.008,
    0.01,
    0.015,
    0.02,
)


class PortalResponseLike(Protocol):
    """KHOA 포털 AJAX 호출에 필요한 최소 응답 프로토콜."""

    status_code: int
    text: str
    content: bytes

    def json(self) -> Any: ...


class PortalSessionLike(Protocol):
    """KHOA 포털 AJAX 호출에 필요한 최소 세션 프로토콜."""

    def post(
        self,
        url: str,
        *,
        data: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> PortalResponseLike: ...


class VworldReverseGeocoderLike(Protocol):
    """pyvworld 역지오코딩 클라이언트에 필요한 최소 프로토콜."""

    def reverse_geocode_latlon(self, lat: float, lon: float, **kwargs: Any) -> Mapping[str, Any]:
        """WGS84 위도/경도 좌표를 VWorld 주소 응답으로 변환합니다."""

        ...


_BEACH_OBSERVATORIES_ZLIB_B64: Final = (
    "eJztvd1uHEuWLvYqBV2pAVUi4ycjM/vOfWDg3PjKl4bR2O5ujBvo6R709LF9bBigqJKGe5M6FKdZUlEq6pAjaVPaoNC1pZI2NaDs"
    "96nMegdjrcifiKxYWRlVlXtseHRVksiKyBUZEevnW9/3P/wfd37/2zu/vPOr//AfGQvv3Lvzx2/+/nd3fnlHJHcXN7N8/zq7vvnF"
    "cjzPDyb583H+8s2de3d++81fvvn1X/7zP8DP/eq//W/+w3+8c+/OH775y51fiiQIw+jenT/86Y93fsl4EsSC3bvzh9/93Td/+PVv"
    "//THv/v1b/70W/iliCUiFCLk7M69O//wzZ9/87s//Pqb3/72z7/7x3+888s7i9k4f/Fk+d2X7OMof/kk/zLJjkeD/OlJ/vRk8Wk2"
    "WE5G2ef72bv5IH95uvj0JPv+eiDZML1z707xJb/+wzd/+f1f/hOMVU6p+p8//fHviv+qJlj+329//49/+eaPv/ndr//+zi/DIKz/"
    "4++/+ctv/ufyiX/3v33zm78YY/3jn/7Tn38D//G//K9/+vMffnvn/7xXm5RzVZt0MdtbfBx1tqUMpJCVLVUgIumypVRpGAoeCqct"
    "84tRdn6b7b9FE16NsuMRmHDx8WLxaQYmXNwcLD6OwIQsEkN+596dP//pm9+W31ANEoeCJbLxv12+Pz+8yL6M8vNJNjvNDn9a3NwM"
    "lBzc1T8Ktnh6kj84Xz6YLuZ7v7hz787//vt/KF+SJGXwTL/93V+++b31TK7fdS9+YUPn4oNFReRefRkFSaSIF+CPv/vmz//Tf+76"
    "BkhhvQHZ1UH2t5vOL0EUiDQxXgIZJu6XIIlDHiku1r8Ek/uLud5HZ4+zR4/z88cDeAOuDuAliNN0mBAvgeBpEobNV6TT95fPnV1O"
    "B0KkQ8btpY7DMHSvYGEAYgXRHD1uX2Zv33z/2mP7ithYuJRTC5eGQoY8Wr9wZ+Xuysdf833cXcvxPDs+g4VLhcTd69wEMBPCgimP"
    "W/ZAynaxB8KU22a86n4KJoGIhXGjRGFK3CgcTkH3BnDfKIuPF/noRzToq6/52RiPQ5wdHofWG8plLJvHX7WGUciFUqv7wndYOBzx"
    "AVaPvFe3ywfn1AWHFiIuOLRXjztEMXNpD/Lzo/x83nl1VaBSZewSFnHnLpEJj8BfiJ275PO7/MP7YpcsH0zz8QHeQT/dLs/f4B10"
    "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"
)


def get_beach_observatories() -> tuple[Observatory, ...]:
    """API 상세 id 36의 주소 포함 해수욕장 관측소 번들 목록을 반환합니다."""

    return BEACH_OBSERVATORIES


def get_builtin_observatory_list(api_id: str = BEACH_OPENAPI_ID) -> tuple[Observatory, ...]:
    """KHOA 포털 OpenAPI 상세 id에 맞는 관측소 번들 목록을 반환합니다."""

    if str(api_id) != BEACH_OPENAPI_ID:
        raise KeyError(f"no bundled KHOA observatory list for OpenAPI detail id {api_id!r}")
    return BEACH_OBSERVATORIES


def fetch_openapi_info(
    api_id: str | int,
    *,
    session: PortalSessionLike | None = None,
    timeout: float = 10.0,
    url: str = KHOA_OPENAPI_INFO_URL,
) -> dict[str, Any]:
    """비표준 AJAX 엔드포인트에서 KHOA 포털 OpenAPI 상세 JSON을 가져옵니다."""

    portal_session = session or cast(PortalSessionLike, requests.Session())
    text_id = str(api_id)
    response = portal_session.post(
        url,
        data={"id": text_id},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{KHOA_OPENAPI_DETAIL_URL}?id={text_id}",
        },
        timeout=timeout,
    )
    _raise_for_portal_status(response, api_id=text_id)
    payload = _decode_portal_json(response, api_id=text_id)
    if not isinstance(payload, Mapping):
        raise KhoaParseError(
            "KHOA portal OpenAPI info response root was not an object",
            endpoint=KHOA_OPENAPI_INFO_URL,
            failure_kind="parse",
        )
    return dict(payload)


def fetch_observatory_list(
    api_id: str | int = BEACH_OPENAPI_ID,
    *,
    session: PortalSessionLike | None = None,
    timeout: float = 10.0,
    include_address: bool = False,
    vworld_client: VworldReverseGeocoderLike | None = None,
    vworld_api_key: str | None = None,
    vworld_domain: str | None = None,
    vworld_env_file: str | PathLike[str] | None = None,
) -> tuple[Observatory, ...]:
    """KHOA 비표준 OpenAPI 상세 엔드포인트에서 관측소 목록을 가져옵니다."""

    payload = fetch_openapi_info(api_id, session=session, timeout=timeout)
    rows = payload.get("observatoryList")
    if not isinstance(rows, list):
        raise KhoaParseError(
            "KHOA portal OpenAPI info response did not contain observatoryList",
            endpoint=KHOA_OPENAPI_INFO_URL,
            failure_kind="parse",
        )
    observatories = _parse_observatories(rows)
    if not include_address:
        return observatories
    return enrich_observatory_addresses(
        observatories,
        vworld_client=vworld_client,
        vworld_api_key=vworld_api_key,
        vworld_domain=vworld_domain,
        vworld_env_file=vworld_env_file,
        timeout=timeout,
    )


def fetch_beach_observatories(
    *,
    session: PortalSessionLike | None = None,
    timeout: float = 10.0,
    include_address: bool = False,
    vworld_client: VworldReverseGeocoderLike | None = None,
    vworld_api_key: str | None = None,
    vworld_domain: str | None = None,
    vworld_env_file: str | PathLike[str] | None = None,
) -> tuple[Observatory, ...]:
    """KHOA OpenAPI 상세 id 36의 live 해수욕장 관측소 목록을 가져옵니다."""

    return fetch_observatory_list(
        BEACH_OPENAPI_ID,
        session=session,
        timeout=timeout,
        include_address=include_address,
        vworld_client=vworld_client,
        vworld_api_key=vworld_api_key,
        vworld_domain=vworld_domain,
        vworld_env_file=vworld_env_file,
    )


def enrich_observatory_addresses(
    observatories: tuple[Observatory, ...],
    *,
    vworld_client: VworldReverseGeocoderLike | None = None,
    vworld_api_key: str | None = None,
    vworld_domain: str | None = None,
    vworld_env_file: str | PathLike[str] | None = None,
    timeout: float = 10.0,
    search_offsets_degrees: tuple[float, ...] = DEFAULT_ADDRESS_SEARCH_OFFSETS_DEGREES,
) -> tuple[Observatory, ...]:
    """pyvworld 역지오코딩 결과를 관측소 목록에 붙입니다."""

    client = _resolve_vworld_client(
        vworld_client,
        vworld_api_key=vworld_api_key,
        vworld_domain=vworld_domain,
        vworld_env_file=vworld_env_file,
        timeout=timeout,
    )
    return tuple(
        observatory.model_copy(
            update=_lookup_vworld_address_fields(
                client,
                observatory,
                search_offsets_degrees=search_offsets_degrees,
            )
        )
        for observatory in observatories
    )


def _resolve_vworld_client(
    vworld_client: VworldReverseGeocoderLike | None,
    *,
    vworld_api_key: str | None,
    vworld_domain: str | None,
    vworld_env_file: str | PathLike[str] | None,
    timeout: float,
) -> VworldReverseGeocoderLike:
    if vworld_client is not None:
        return vworld_client
    try:
        module = importlib.import_module("pyvworld")
    except ModuleNotFoundError as exc:
        raise KhoaRequestError(
            "주소 보강에는 pyvworld 패키지가 필요합니다.",
            endpoint="https://api.vworld.kr/req/address",
            failure_kind="request",
            retryable=False,
        ) from exc

    client_class = cast(Any, module).VworldClient
    kwargs: dict[str, Any] = {"timeout": timeout}
    if vworld_api_key is not None:
        kwargs["api_key"] = vworld_api_key
    if vworld_domain is not None:
        kwargs["domain"] = vworld_domain
    if vworld_env_file is not None:
        return cast(
            VworldReverseGeocoderLike,
            client_class.from_env_file(vworld_env_file, **kwargs),
        )
    return cast(VworldReverseGeocoderLike, client_class(**kwargs))


def _lookup_vworld_address_fields(
    client: VworldReverseGeocoderLike,
    observatory: Observatory,
    *,
    search_offsets_degrees: tuple[float, ...],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    first_match: tuple[float, float, float, str] | None = None
    found_parcel = False
    found_road = False

    for lat, lon, distance_m, match_type in _nearby_lookup_points(
        observatory.latitude,
        observatory.longitude,
        search_offsets_degrees,
    ):
        try:
            payload = client.reverse_geocode_latlon(
                lat,
                lon,
                type="both",
                zipcode=True,
                simple=False,
            )
        except Exception as exc:
            if _is_vworld_not_found(exc):
                continue
            raise KhoaRequestError(
                f"VWorld 역지오코딩 호출 실패: {observatory.id} {observatory.name}",
                endpoint="https://api.vworld.kr/req/address",
                failure_kind="request",
                retryable=True,
            ) from exc

        fields = _extract_vworld_address_fields(payload)
        if fields:
            if first_match is None:
                first_match = (lat, lon, distance_m, match_type)
            if not found_parcel and (
                fields.get("legal_dong_code") or fields.get("parcel_address")
            ):
                _copy_missing(
                    merged,
                    fields,
                    ("legal_dong_code", "parcel_address", "zipcode", "detail_address"),
                )
                found_parcel = True
            if not found_road and (
                fields.get("road_address_code") or fields.get("road_address")
            ):
                _copy_missing(
                    merged,
                    fields,
                    ("road_address_code", "road_address", "zipcode", "detail_address"),
                )
                found_road = True
            if found_parcel and found_road:
                break

    if merged and first_match is not None:
        lat, lon, distance_m, match_type = first_match
        merged["address_latitude"] = lat
        merged["address_longitude"] = lon
        merged["address_distance_m"] = round(distance_m, 3)
        merged["address_match_type"] = match_type
        merged["address_source"] = "vworld"
        return merged

    return {"address_match_type": "not_found", "address_source": "vworld"}


def _extract_vworld_address_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    items = _vworld_result_items(payload)
    parcel = _find_vworld_result(items, "parcel")
    road = _find_vworld_result(items, "road")
    primary = parcel or road
    parcel_structure = _structure(parcel)
    road_structure = _structure(road)
    primary_structure = _structure(primary)

    fields = {
        "legal_dong_code": _first_text(
            _field(parcel_structure, "level4LC"),
            _field(parcel_structure, "legalDongCode"),
            _field(parcel_structure, "bjdCode"),
            _field(parcel, "legal_dong_code"),
            _field(parcel, "legalDongCode"),
            _field(parcel, "bjdCode"),
        ),
        "road_address_code": _first_text(
            _field(road_structure, "roadCode"),
            _field(road_structure, "roadCd"),
            _field(road_structure, "rnMgtSn"),
            _field(road_structure, "level4LC"),
            _field(road, "road_address_code"),
            _field(road, "roadAddressCode"),
            _field(road, "roadCode"),
        ),
        "parcel_address": _field(parcel, "text"),
        "road_address": _field(road, "text"),
        "detail_address": _first_text(
            _field(parcel_structure, "detail"),
            _field(primary_structure, "detail"),
            _field(road_structure, "detail"),
            _field(primary, "detail"),
        ),
        "zipcode": _first_text(_field(parcel, "zipcode"), _field(road, "zipcode")),
    }
    return {key: value for key, value in fields.items() if value is not None}


def _vworld_result_items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    response = _as_mapping(payload.get("response"))
    result = response.get("result") if response is not None else payload.get("result")
    if result is None:
        return ()
    if isinstance(result, list):
        return tuple(item for item in result if isinstance(item, Mapping))
    if isinstance(result, Mapping):
        items = result.get("items")
        if isinstance(items, list):
            return tuple(item for item in items if isinstance(item, Mapping))
        item = result.get("item")
        if isinstance(item, list):
            return tuple(value for value in item if isinstance(value, Mapping))
        if isinstance(item, Mapping):
            return (item,)
        return (result,)
    return ()


def _find_vworld_result(
    items: tuple[Mapping[str, Any], ...],
    result_type: str,
) -> Mapping[str, Any] | None:
    for item in items:
        item_type = _field(item, "type")
        if item_type is not None and item_type.lower() == result_type:
            return item
    return None


def _copy_missing(
    target: dict[str, Any],
    source: Mapping[str, Any],
    keys: tuple[str, ...],
) -> None:
    for key in keys:
        if key not in target and source.get(key) is not None:
            target[key] = source[key]


def _structure(item: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if item is None:
        return {}
    structure = item.get("structure")
    return structure if isinstance(structure, Mapping) else {}


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _field(mapping: Mapping[str, Any] | None, key: str) -> str | None:
    if mapping is None:
        return None
    value = mapping.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_text(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _nearby_lookup_points(
    latitude: float,
    longitude: float,
    offsets_degrees: tuple[float, ...],
) -> tuple[tuple[float, float, float, str], ...]:
    points: list[tuple[float, float, float, str]] = []
    seen: set[tuple[float, float]] = set()
    for offset in offsets_degrees:
        if offset < 0:
            continue
        candidates = (
            ((0.0, 0.0),)
            if offset == 0
            else (
                (offset, 0.0),
                (-offset, 0.0),
                (0.0, offset),
                (0.0, -offset),
                (offset, offset),
                (offset, -offset),
                (-offset, offset),
                (-offset, -offset),
            )
        )
        ring: list[tuple[float, float, float, str]] = []
        for lat_delta, lon_delta in candidates:
            lat = latitude + lat_delta
            lon = longitude + lon_delta
            key = (round(lat, 7), round(lon, 7))
            if key in seen:
                continue
            seen.add(key)
            distance_m = _distance_m(latitude, longitude, lat, lon)
            match_type = "exact" if distance_m == 0 else "nearby"
            ring.append((lat, lon, distance_m, match_type))
        points.extend(sorted(ring, key=lambda item: item[2]))
    return tuple(points)


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    lat_delta = math.radians(lat2 - lat1)
    lon_delta = math.radians(lon2 - lon1)
    half_chord = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(lon_delta / 2) ** 2
    )
    return 2 * radius_m * math.asin(math.sqrt(half_chord))


def _is_vworld_not_found(exc: Exception) -> bool:
    return exc.__class__.__name__ == "VworldNoDataError" or "NOT_FOUND" in str(exc)


def _decode_portal_json(response: PortalResponseLike, *, api_id: str) -> Any:
    try:
        if response.content:
            return json.loads(response.content.decode("utf-8"))
        return response.json()
    except (UnicodeDecodeError, ValueError) as exc:
        raise KhoaParseError(
            f"KHOA portal OpenAPI info {api_id} was not valid JSON",
            endpoint=KHOA_OPENAPI_INFO_URL,
            failure_kind="parse",
        ) from exc


def _raise_for_portal_status(response: PortalResponseLike, *, api_id: str) -> None:
    status = response.status_code
    text = response.text[:300]
    if 400 <= status < 500:
        raise KhoaRequestError(
            f"KHOA portal OpenAPI info {api_id} returned HTTP {status}: {text}",
            endpoint=KHOA_OPENAPI_INFO_URL,
            status_code=status,
            failure_kind="request",
            retryable=False,
        )
    if 500 <= status < 600:
        raise KhoaServerError(
            f"KHOA portal OpenAPI info {api_id} returned HTTP {status}: {text}",
            endpoint=KHOA_OPENAPI_INFO_URL,
            status_code=status,
            failure_kind="server",
            retryable=True,
        )


def _parse_observatories(rows: list[Any]) -> tuple[Observatory, ...]:
    observatories: list[Observatory] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise KhoaParseError(
                "KHOA portal observatory row was not an object",
                endpoint=KHOA_OPENAPI_INFO_URL,
                failure_kind="parse",
            )
        try:
            observatories.append(Observatory.from_raw(row))
        except (KeyError, ValueError) as exc:
            raise KhoaParseError(
                "KHOA portal observatory row was missing required fields",
                endpoint=KHOA_OPENAPI_INFO_URL,
                failure_kind="parse",
            ) from exc
    return tuple(observatories)


def _load_embedded_beach_observatories() -> tuple[Observatory, ...]:
    raw = zlib.decompress(base64.b64decode(_BEACH_OBSERVATORIES_ZLIB_B64)).decode("utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise RuntimeError("embedded KHOA beach observatory payload must be a list")
    return _parse_observatories(payload)


BEACH_OBSERVATORIES: Final[tuple[Observatory, ...]] = _load_embedded_beach_observatories()
BEACH_OBSERVATORY_COUNT: Final = len(BEACH_OBSERVATORIES)
