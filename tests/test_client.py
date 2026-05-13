from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest
from kraddr.base import Address

from khoa import (
    BeachIndexPlace,
    BeachSearchResult,
    KhoaClient,
    KhoaRequestError,
    MarineIndexPlace,
    RomsPrediction,
)
from khoa.exceptions import KhoaAuthError, KhoaNoDataError

from .conftest import FakeResponse, khoa_payload


class FakeVworldClient:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def reverse_geocode_latlon(self, lat: float, lon: float, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append({"lat": lat, "lon": lon, "kwargs": dict(kwargs)})
        return self.payload


def test_fetch_builds_request_and_normalizes_items(fake_client_factory):
    row = {"predcDt": "2024-11-01 00:00:00", "lat": "34.01", "lot": "123.2"}
    client, session = fake_client_factory(FakeResponse(khoa_payload(row)))

    page = client.fetch(
        "roms",
        ymin=34.0,
        ymax=34.1,
        xmin=123.2,
        xmax=123.3,
        include=("lat", "lot"),
        num_of_rows=5,
    )

    call = session.calls[0]
    assert call["url"].endswith("/roms/GetRomsApiService")
    assert call["params"]["serviceKey"] == "TEST_KEY"
    assert call["params"]["type"] == "json"
    assert call["params"]["numOfRows"] == 5
    assert call["params"]["include"] == "lat,lot"
    assert page.items[0]["lat"] == "34.01"
    assert page.context is not None
    assert page.context.endpoint == "roms/GetRomsApiService"
    assert "serviceKey" not in page.context.request_params


def test_snake_case_aliases_and_dynamic_service_method(fake_client_factory):
    client, session = fake_client_factory(FakeResponse(khoa_payload([])))

    page = client.dt_recent(obs_code="DT_0001", req_date=date(2026, 5, 7), min=10)

    params = session.calls[0]["params"]
    assert page.items == ()
    assert session.calls[0]["url"].endswith("/dtRecent/GetDTRecentApiService")
    assert params["obsCode"] == "DT_0001"
    assert params["reqDate"] == "20260507"
    assert params["min"] == 10


def test_required_param_validation(fake_client_factory):
    client, _session = fake_client_factory(FakeResponse(khoa_payload([])))

    with pytest.raises(KhoaRequestError, match="obsCode"):
        client.fetch("dt_recent")


def test_roms_typed_helper(fake_client_factory):
    row = {
        "predcDt": "2024-11-01 00:00:00",
        "lat": "39.19335",
        "lot": "118.02332",
        "crdir": "99.71",
        "crsp": "0.07",
        "wtem": "15.45",
    }
    client, _session = fake_client_factory(FakeResponse(khoa_payload(row)))

    page = client.roms(ymin=34.0, ymax=34.1, xmin=123.2, xmax=123.3)

    item = page.items[0]
    assert isinstance(item, RomsPrediction)
    assert item.predicted_at is not None
    assert item.predicted_at.year == 2024
    assert item.latitude == 39.19335
    assert item.longitude == 118.02332
    assert item.water_temperature_c == 15.45


def test_beach_index_accepts_top_level_header_body_payload(fake_client_factory):
    row = {
        "bbchNm": "대천해수욕장",
        "lat": 36.31,
        "lot": 126.513,
        "predcYmd": "2026-05-13",
        "predcNoonSeCd": "오전",
    }
    client, session = fake_client_factory(FakeResponse(_top_level_khoa_payload(row)))

    page = client.beach_index(num_of_rows=1)

    assert session.calls[0]["url"].endswith("/fcstBeachv2/GetFcstBeachApiServicev2")
    place = page.items[0]
    assert isinstance(place, BeachIndexPlace)
    assert place.name == "대천해수욕장"
    assert place.forecasts[0].forecast_period == "오전"
    assert page.total_count == 1


def test_beach_index_can_include_vworld_address(fake_client_factory):
    row = {
        "bbchNm": "해운대해수욕장",
        "lat": 35.158,
        "lot": 129.159,
        "predcYmd": "2026-05-13",
        "predcNoonSeCd": "오전",
    }
    client, _session = fake_client_factory(FakeResponse(_top_level_khoa_payload([row, row])))
    vworld = FakeVworldClient(_vworld_address_payload())

    page = client.beach_index(include_address=True, vworld_client=vworld, num_of_rows=2)

    first = page.items[0]
    assert len(page.items) == 1
    assert first.id == "BCH001"
    assert first.name == "해운대해수욕장"
    assert len(first.forecasts) == 2
    assert isinstance(first.address, Address)
    assert first.legal_dong_code == "2635010500"
    assert first.road_address_code == "26350530419929900026400000"
    assert first.road_name_code == "263504199299"
    assert first.parcel_address == "부산광역시 해운대구 우동 622-8"
    assert first.road_address == "부산광역시 해운대구 해운대해변로 264"
    assert first.detail_address == "해운대해수욕장"
    assert first.zipcode == "48094"
    assert first.address_latitude == pytest.approx(35.1585)
    assert first.address_longitude == pytest.approx(129.1585)
    assert first.address_match_type == "nearby"
    assert first.address_source == "vworld"
    assert len(vworld.calls) == 1


def test_beach_search_calls_direct_endpoint_and_returns_dto(fake_client_factory):
    payload = {
        "result": {
            "meta": {
                "beach_code": "BCH001",
                "beach_name": "Haeundae Beach",
                "obs_post_name": "Haeundae Beach",
            },
            "data": [
                {
                    "tide": None,
                    "water_temp": "16.2",
                    "wind_speed": "2.5",
                    "wind_direct": "SSW",
                    "obs_time": "2026-05-13 18:40",
                }
            ],
        }
    }
    client, session = fake_client_factory(FakeResponse(payload))

    result = client.beach_search("BCH001", service_key="DIRECT_KEY")

    call = session.calls[0]
    assert call["url"].endswith("/beach/search.do")
    assert call["params"]["ServiceKey"] == "DIRECT_KEY"
    assert call["params"]["BeachCode"] == "BCH001"
    assert isinstance(result, BeachSearchResult)
    assert result.id == "BCH001"
    assert result.name == "Haeundae Beach"
    assert result.lat is not None
    assert isinstance(result.address, Address)
    observation = result.observations[0]
    assert observation.water_temperature_c == 16.2
    assert observation.wind_speed_m_s == 2.5
    assert observation.observed_at is not None


def test_surfing_index_groups_places_and_enriches_address_once(fake_client_factory):
    rows = [
        {
            "surfPlcNm": "Surf A",
            "lat": "35.0",
            "lot": "129.0",
            "predcYmd": "20260513",
            "predcNoonSeCd": "AM",
            "avgWvhgt": "0.4",
            "totalIndex": "80",
        },
        {
            "surfPlcNm": "Surf A",
            "lat": "35.0",
            "lot": "129.0",
            "predcYmd": "20260513",
            "predcNoonSeCd": "PM",
            "avgWvhgt": "0.5",
            "totalIndex": "82",
        },
        {
            "surfPlcNm": "Surf B",
            "lat": "36.0",
            "lot": "128.0",
            "predcYmd": "20260513",
            "avgWvhgt": "0.2",
            "totalIndex": "60",
        },
    ]
    client, session = fake_client_factory(FakeResponse(khoa_payload(rows)))
    vworld = FakeVworldClient(_vworld_address_payload())

    page = client.surfing_index(include_address=True, vworld_client=vworld, num_of_rows=3)

    assert session.calls[0]["url"].endswith("/fcstSurfingv2/GetFcstSurfingApiServicev2")
    assert len(page.items) == 2
    first = page.items[0]
    assert isinstance(first, MarineIndexPlace)
    assert first.service_key == "surfing_index"
    assert first.name == "Surf A"
    assert len(first.forecasts) == 2
    assert first.forecasts[0].total_index == 80
    assert first.forecasts[0].metrics["avgWvhgt"] == "0.4"
    assert isinstance(first.address, Address)
    assert len(vworld.calls) == 2


def test_iter_pages_stops_after_total_count(fake_client_factory):
    client, session = fake_client_factory(
        FakeResponse(
            khoa_payload([{"a": "1"}, {"a": "2"}], page_no=1, num_of_rows=2, total_count=3)
        ),
        FakeResponse(khoa_payload({"a": "3"}, page_no=2, num_of_rows=2, total_count=3)),
    )

    pages = list(
        client.iter_pages(
            "roms",
            ymin=34.0,
            ymax=34.1,
            xmin=123.2,
            xmax=123.3,
            num_of_rows=2,
        )
    )

    assert [page.page_no for page in pages] == [1, 2]
    assert [call["params"]["pageNo"] for call in session.calls] == [1, 2]


def test_first_raises_no_data(fake_client_factory):
    client, _session = fake_client_factory(FakeResponse(khoa_payload(None, result_code="03")))

    with pytest.raises(KhoaNoDataError):
        client.first(
            "roms",
            ymin=34.0,
            ymax=34.1,
            xmin=123.2,
            xmax=123.3,
        )


def test_env_constructor_errors(monkeypatch):
    names = (
        "KHOA_SERVICE_KEY",
        "KHOA_API_KEY",
        "DATA_GO_KR_SERVICE_KEY",
        "PUBLIC_DATA_SERVICE_KEY",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(KhoaAuthError):
        KhoaClient()


def test_constructor_accepts_api_key_parameter():
    client = KhoaClient(api_key="TEST_KEY", retries=0)

    assert client.service_key == "TEST_KEY"


def _top_level_khoa_payload(
    item: Any,
    *,
    result_code: str = "00",
    result_msg: str = "NORMAL_SERVICE",
    page_no: int = 1,
    num_of_rows: int = 10,
    total_count: int | None = None,
) -> dict[str, Any]:
    inferred_total = len(item) if isinstance(item, list) else 1
    body: dict[str, Any] = {
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "totalCount": total_count if total_count is not None else inferred_total,
    }
    if item is not None:
        body["items"] = {"item": item}
    return {
        "header": {"resultCode": result_code, "resultMsg": result_msg},
        "body": body,
    }


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
                        "level4LC": "2635010500",
                        "detail": "",
                    },
                },
                {
                    "type": "road",
                    "text": "부산광역시 해운대구 해운대해변로 264",
                    "zipcode": "48094",
                    "structure": {
                        "level4LC": "4199299",
                        "level4AC": "2635053000",
                        "level5": "264",
                        "detail": "해운대해수욕장",
                    },
                },
            ],
        }
    }
