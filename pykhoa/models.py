"""pykhoa가 사용자에게 반환하는 Pydantic 응답 모델."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pykrtour import (
    Address,
    AddressRegion,
    JibunAddress,
    LegalDongCode,
    PlaceCoordinate,
    RoadNameAddress,
    RoadNameAddressCode,
    RoadNameCode,
)

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
    coordinate: PlaceCoordinate
    data_type: str | None = None
    address: Address | None = None
    address_coordinate: PlaceCoordinate | None = None
    address_distance_m: float | None = None
    address_match_type: str | None = None
    address_source: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def latitude(self) -> float:
        """호환성을 위해 제공하는 위도 값."""

        return self.coordinate.lat

    @property
    def longitude(self) -> float:
        """호환성을 위해 제공하는 경도 값."""

        return self.coordinate.lon

    @property
    def lat(self) -> float:
        """KHOA 포털 원문 필드명에 맞춘 위도 별칭."""

        return self.coordinate.lat

    @property
    def lon(self) -> float:
        """KHOA 포털 원문 필드명에 맞춘 경도 별칭."""

        return self.coordinate.lon

    @property
    def address_latitude(self) -> float | None:
        """주소 조회에 사용한 보정 좌표의 위도입니다."""

        return self.address_coordinate.lat if self.address_coordinate is not None else None

    @property
    def address_longitude(self) -> float | None:
        """주소 조회에 사용한 보정 좌표의 경도입니다."""

        return self.address_coordinate.lon if self.address_coordinate is not None else None

    @property
    def legal_dong_code(self) -> str | None:
        """주소의 법정동코드입니다."""

        return self.address.legal_dong_code if self.address is not None else None

    @property
    def road_address_code(self) -> str | None:
        """도로명주소관리번호 26자리 코드입니다."""

        road_name = self.address.road_name if self.address is not None else None
        code = road_name.road_name_address_code if road_name is not None else None
        return code.code if code is not None else None

    @property
    def road_name_code(self) -> str | None:
        """도로명코드 12자리 값입니다."""

        road_name = self.address.road_name if self.address is not None else None
        code = road_name.effective_road_name_code if road_name is not None else None
        return code.code if code is not None else None

    @property
    def parcel_address(self) -> str | None:
        """지번주소 문자열입니다."""

        jibun = self.address.jibun if self.address is not None else None
        return jibun.address if jibun is not None else None

    @property
    def road_address(self) -> str | None:
        """도로명주소 문자열입니다."""

        road_name = self.address.road_name if self.address is not None else None
        return road_name.address if road_name is not None else None

    @property
    def detail_address(self) -> str | None:
        """상세주소 문자열입니다."""

        if self.address is None:
            return None
        if self.address.detail_address is not None:
            return self.address.detail_address
        road_name = self.address.road_name
        return road_name.building_name if road_name is not None else None

    @property
    def zipcode(self) -> str | None:
        """우편번호입니다."""

        return self.address.effective_postal_code if self.address is not None else None

    @classmethod
    def from_raw(cls, row: Mapping[str, Any]) -> Observatory:
        """KHOA 포털 관측소 원문 행을 모델로 변환합니다."""

        coordinate_value = row.get("coordinate")
        if isinstance(coordinate_value, PlaceCoordinate):
            coordinate = coordinate_value
        elif isinstance(coordinate_value, Mapping):
            coordinate = PlaceCoordinate.model_validate(coordinate_value)
        else:
            latitude = to_float_or_none(row.get("lat"))
            longitude = to_float_or_none(row.get("lon"))
            if latitude is None or longitude is None:
                raise ValueError("KHOA observatory row requires lat/lon")
            coordinate = PlaceCoordinate(lat=latitude, lon=longitude)

        address_coordinate: PlaceCoordinate | None
        address_coordinate_value = row.get("address_coordinate")
        if isinstance(address_coordinate_value, PlaceCoordinate):
            address_coordinate = address_coordinate_value
        elif isinstance(address_coordinate_value, Mapping):
            address_coordinate = PlaceCoordinate.model_validate(address_coordinate_value)
        else:
            address_latitude = to_float_or_none(row.get("address_latitude"))
            address_longitude = to_float_or_none(row.get("address_longitude"))
            address_coordinate = (
                PlaceCoordinate(lat=address_latitude, lon=address_longitude)
                if address_latitude is not None and address_longitude is not None
                else None
            )

        address: Address | None
        address_value = row.get("address")
        if isinstance(address_value, Address):
            address = address_value
        elif isinstance(address_value, Mapping):
            address = Address.model_validate(address_value)
        else:
            legal_dong_code = _row_text(row, "legal_dong_code", "legalDongCode", "bjdCode")
            road_address_code = _row_text(row, "road_address_code", "roadAddressCode")
            road_name_code = _row_text(row, "road_name_code", "roadNameCode", "rnMgtSn")
            parcel_address = _row_text(row, "parcel_address", "parcelAddress")
            road_address = _row_text(row, "road_address", "roadAddress")
            detail_address = _row_text(row, "detail_address", "detailAddress")
            zipcode = _row_text(row, "zipcode", "zip_code", "zipCode")
            legal_dong = (
                LegalDongCode(code=legal_dong_code) if legal_dong_code is not None else None
            )
            road_address_management_code = (
                RoadNameAddressCode(code=road_address_code)
                if road_address_code is not None
                else None
            )
            road_name_management_code = (
                RoadNameCode(code=road_name_code) if road_name_code is not None else None
            )
            region = (
                AddressRegion.from_legal_dong_code(legal_dong)
                if legal_dong is not None
                else None
            )
            jibun = (
                JibunAddress(
                    address=parcel_address,
                    legal_dong_code=legal_dong,
                    postal_code=zipcode,
                )
                if legal_dong is not None or parcel_address is not None
                else None
            )
            road_name = (
                RoadNameAddress(
                    address=road_address,
                    road_name_code=road_name_management_code,
                    road_name_address_code=road_address_management_code,
                    building_name=detail_address,
                    postal_code=zipcode,
                )
                if (
                    road_address_code is not None
                    or road_name_code is not None
                    or road_address is not None
                )
                else None
            )
            address = (
                Address(
                    region=region,
                    jibun=jibun,
                    road_name=road_name,
                    postal_code=zipcode,
                    detail_address=detail_address,
                )
                if any((region, jibun, road_name, zipcode, detail_address))
                else None
            )

        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            data_type=strip_or_none(row.get("data_type")),
            coordinate=coordinate,
            address=address,
            address_coordinate=address_coordinate,
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
