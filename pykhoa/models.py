"""pykhoa가 사용자에게 반환하는 Pydantic 응답 모델."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ._convert import strip_or_none, to_datetime_or_none, to_float_or_none

T = TypeVar("T")
RawRecord = Mapping[str, Any]


class KhoaModel(BaseModel):
    """pykhoa 응답 모델의 공통 불변 기반 클래스."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ResponseContext(KhoaModel):
    """인증키를 노출하지 않는 KHOA API 호출 메타데이터."""

    provider: str = "data.go.kr"
    service_key: str
    service_title: str
    service_path: str
    operation: str
    endpoint: str
    request_url: str
    request_params: dict[str, Any] = Field(default_factory=dict)
    collected_at: datetime


class Observatory(KhoaModel):
    """KHOA 포털 관측소/지점 목록의 한 항목."""

    id: str
    name: str
    latitude: float
    longitude: float
    data_type: str | None = None
    legal_dong_code: str | None = None
    road_address_code: str | None = None
    road_name_code: str | None = None
    parcel_address: str | None = None
    road_address: str | None = None
    detail_address: str | None = None
    zipcode: str | None = None
    address_latitude: float | None = None
    address_longitude: float | None = None
    address_distance_m: float | None = None
    address_match_type: str | None = None
    address_source: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def lat(self) -> float:
        """KHOA 포털 원문 필드명에 맞춘 위도 별칭."""

        return self.latitude

    @property
    def lon(self) -> float:
        """KHOA 포털 원문 필드명에 맞춘 경도 별칭."""

        return self.longitude

    @classmethod
    def from_raw(cls, row: Mapping[str, Any]) -> Observatory:
        """KHOA 포털 관측소 원문 행을 모델로 변환합니다."""

        latitude = to_float_or_none(row.get("lat"))
        longitude = to_float_or_none(row.get("lon"))
        if latitude is None or longitude is None:
            raise ValueError("KHOA observatory row requires lat/lon")
        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            data_type=strip_or_none(row.get("data_type")),
            latitude=latitude,
            longitude=longitude,
            legal_dong_code=_row_text(row, "legal_dong_code", "legalDongCode", "bjdCode"),
            road_address_code=_row_text(row, "road_address_code", "roadAddressCode"),
            road_name_code=_row_text(row, "road_name_code", "roadNameCode", "rnMgtSn"),
            parcel_address=_row_text(row, "parcel_address", "parcelAddress"),
            road_address=_row_text(row, "road_address", "roadAddress"),
            detail_address=_row_text(row, "detail_address", "detailAddress"),
            zipcode=_row_text(row, "zipcode", "zip_code", "zipCode"),
            address_latitude=to_float_or_none(row.get("address_latitude")),
            address_longitude=to_float_or_none(row.get("address_longitude")),
            address_distance_m=to_float_or_none(row.get("address_distance_m")),
            address_match_type=_row_text(row, "address_match_type", "addressMatchType"),
            address_source=_row_text(row, "address_source", "addressSource"),
            raw=dict(row),
        )


class Page(KhoaModel, Generic[T]):
    """KHOA 페이지네이션 응답의 한 페이지."""

    items: tuple[T, ...]
    total_count: int = 0
    page_no: int = 1
    num_of_rows: int = 10
    raw: dict[str, Any] = Field(default_factory=dict)
    context: ResponseContext | None = None

    @property
    def has_next_page(self) -> bool:
        return self.page_no * self.num_of_rows < self.total_count

    @property
    def next_page_no(self) -> int | None:
        return self.page_no + 1 if self.has_next_page else None

    @property
    def endpoint(self) -> str | None:
        return self.context.endpoint if self.context else None

    @property
    def request_params(self) -> dict[str, Any]:
        return dict(self.context.request_params) if self.context else {}


class RomsPrediction(KhoaModel):
    """ROMS 수치예측 엔드포인트의 typed 행 모델."""

    predicted_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    current_direction_deg: float | None = None
    current_speed_cm_s: float | None = None
    water_temperature_c: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, row: Mapping[str, Any]) -> RomsPrediction:
        return cls(
            predicted_at=to_datetime_or_none(row.get("predcDt")),
            latitude=to_float_or_none(row.get("lat")),
            longitude=to_float_or_none(row.get("lot")),
            current_direction_deg=to_float_or_none(row.get("crdir")),
            current_speed_cm_s=to_float_or_none(row.get("crsp")),
            water_temperature_c=to_float_or_none(row.get("wtem")),
            raw=dict(row),
        )


def _row_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        text = strip_or_none(row.get(key))
        if text is not None:
            return text
    return None
