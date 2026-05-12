from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from kraddr.base import Address, PlaceCoordinate

from khoa import (
    BEACH_INFO_UPDATE_INTERVAL_MINUTES,
    BEACH_OBSERVATORIES,
    BEACH_OBSERVATORY_COUNT,
    BEACH_OPENAPI_ID,
    KHOA_OPENAPI_INFO_URL,
    enrich_observatory_addresses,
    fetch_observatory_list,
    get_beach_observatories,
    get_builtin_observatory_list,
)


class FakePortalResponse:
    def __init__(self, payload: Any, *, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)
        self.content = self.text.encode("utf-8")

    def json(self) -> Any:
        return self.payload


class FakePortalSession:
    def __init__(self, response: FakePortalResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        data: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> FakePortalResponse:
        self.calls.append(
            {
                "url": url,
                "data": dict(data),
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        return self.response


class FakeVworldClient:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def reverse_geocode_latlon(self, lat: float, lon: float, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append({"lat": lat, "lon": lon, "kwargs": dict(kwargs)})
        return self.payload


def test_bundled_beach_observatories_are_available():
    assert BEACH_OBSERVATORY_COUNT == 356
    assert len(BEACH_OBSERVATORIES) == 356
    assert BEACH_INFO_UPDATE_INTERVAL_MINUTES == 30

    haeundae = next(item for item in BEACH_OBSERVATORIES if item.id == "BCH001")
    assert haeundae.name == "해운대해수욕장"
    assert haeundae.coordinate == PlaceCoordinate(lat=35.158, lon=129.159)
    assert isinstance(haeundae.address, Address)
    assert haeundae.lat == 35.158
    assert haeundae.lon == 129.159
    assert hasattr(haeundae, "legal_dong_code")
    assert hasattr(haeundae, "road_address_code")
    assert hasattr(haeundae, "detail_address")


def test_builtin_observatory_lookup_by_openapi_id():
    assert get_builtin_observatory_list(BEACH_OPENAPI_ID) is BEACH_OBSERVATORIES


def test_fetch_observatory_list_uses_nonstandard_portal_endpoint():
    session = FakePortalSession(
        FakePortalResponse(
            {
                "observatoryList": [
                    {
                        "id": "BCH001",
                        "name": "해운대해수욕장",
                        "data_type": "BEACH",
                        "lat": 35.158,
                        "lon": 129.159,
                    }
                ]
            }
        )
    )

    observatories = fetch_observatory_list(session=session)

    assert session.calls[0]["url"] == KHOA_OPENAPI_INFO_URL
    assert session.calls[0]["data"] == {"id": BEACH_OPENAPI_ID}
    assert session.calls[0]["headers"]["X-Requested-With"] == "XMLHttpRequest"
    assert observatories[0].id == "BCH001"
    assert observatories[0].name == "해운대해수욕장"
    assert observatories[0].coordinate == PlaceCoordinate(lat=35.158, lon=129.159)


def test_fetch_observatory_list_can_enrich_address_from_vworld_payload():
    session = FakePortalSession(
        FakePortalResponse(
            {
                "observatoryList": [
                    {
                        "id": "BCH001",
                        "name": "해운대해수욕장",
                        "data_type": "BEACH",
                        "lat": 35.158,
                        "lon": 129.159,
                    }
                ]
            }
        )
    )
    vworld = FakeVworldClient(_vworld_address_payload())

    observatories = fetch_observatory_list(
        session=session,
        include_address=True,
        vworld_client=vworld,
    )

    assert isinstance(observatories[0].address, Address)
    assert observatories[0].legal_dong_code == "2635010500"
    assert observatories[0].address is not None
    assert observatories[0].address.legal_dong_code == "2635010500"
    assert observatories[0].road_address_code == "26350530419929900026400000"
    assert observatories[0].road_name_code == "263504199299"
    assert observatories[0].parcel_address == "부산광역시 해운대구 우동 622-8"
    assert observatories[0].road_address == "부산광역시 해운대구 해운대해변로 264"
    assert observatories[0].detail_address == "해운대해수욕장"
    assert observatories[0].zipcode == "48094"
    assert observatories[0].coordinate == PlaceCoordinate(lat=35.158, lon=129.159)
    assert observatories[0].address_coordinate == PlaceCoordinate(lat=35.158, lon=129.159)
    assert observatories[0].address_match_type == "exact"
    assert vworld.calls[0]["lat"] == 35.158
    assert vworld.calls[0]["lon"] == 129.159
    assert vworld.calls[0]["kwargs"]["type"] == "both"
    assert vworld.calls[0]["kwargs"]["zipcode"] is True
    assert vworld.calls[0]["kwargs"]["simple"] is False


def test_get_beach_observatories_returns_bundled_address_fields():
    observatories = get_beach_observatories()

    haeundae = next(item for item in observatories if item.id == "BCH001")
    assert isinstance(haeundae.address, Address)
    assert haeundae.legal_dong_code
    assert haeundae.road_address_code
    assert len(haeundae.road_address_code) == 26
    assert haeundae.road_name_code
    assert haeundae.coordinate == PlaceCoordinate(lat=35.158, lon=129.159)
    assert isinstance(haeundae.address_coordinate, PlaceCoordinate)
    assert haeundae.parcel_address
    assert haeundae.detail_address
    assert haeundae.address_source == "vworld"
    assert all(
        len(item.road_address_code) == 26
        for item in observatories
        if item.road_address_code
    )


def test_enrich_observatory_addresses_accepts_small_tuple():
    vworld = FakeVworldClient(_vworld_address_payload())

    observatories = enrich_observatory_addresses(BEACH_OBSERVATORIES[:1], vworld_client=vworld)

    assert observatories[0].legal_dong_code == "2635010500"
    assert observatories[0].address_coordinate == observatories[0].coordinate
    assert len(vworld.calls) == 1


def _vworld_address_payload() -> Mapping[str, Any]:
    return {
        "response": {
            "status": "OK",
            "result": [
                {
                    "type": "parcel",
                    "text": "부산광역시 해운대구 우동 622-8",
                    "zipcode": "48094",
                    "structure": {
                        "level4L": "우동",
                        "level4LC": "2635010500",
                        "detail": "",
                    },
                },
                {
                    "type": "road",
                    "text": "부산광역시 해운대구 해운대해변로 264",
                    "zipcode": "48094",
                    "structure": {
                        "level4L": "해운대해변로",
                        "level4LC": "4199299",
                        "level4AC": "2635053000",
                        "level5": "264",
                        "detail": "해운대해수욕장",
                    },
                },
            ],
        }
    }
