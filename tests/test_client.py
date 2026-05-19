from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest
from kraddr.base import Address

from khoa import (
    AsyncKhoaClient,
    BeachIndexPlace,
    BeachSearchResult,
    KhoaClient,
    KhoaRequestError,
    MarineIndexPlace,
    OceanBeachInfo,
    RomsPrediction,
    get_api_catalog,
    get_api_catalog_entry,
    get_service_key,
)
from khoa.exceptions import KhoaAuthError, KhoaNoDataError

from .conftest import FakeResponse, FakeSession, khoa_payload


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


@pytest.mark.asyncio
async def test_aio_client_fetch_uses_krheritage_style_api() -> None:
    session = FakeSession(
        [
            FakeResponse(khoa_payload({"foo": "bar"})),
            FakeResponse(khoa_payload(None, result_code="03")),
        ]
    )

    async with KhoaClient.aio(api_key="TEST_KEY", session=session, retries=0) as client:
        assert isinstance(client, AsyncKhoaClient)
        page = await client.fetch("vortex", num_of_rows=1)
        dynamic_page = await client.vortex(num_of_rows=1)

    assert page.items == ({"foo": "bar"},)
    assert dynamic_page.items == ()
    assert client.closed
    assert [call["params"]["serviceKey"] for call in session.calls] == ["TEST_KEY", "TEST_KEY"]


@pytest.mark.asyncio
async def test_aio_client_iterates_oceans_beach_info_pages() -> None:
    session = FakeSession(
        [
            FakeResponse(
                _top_level_khoa_payload(
                    {"sidoNm": "제주", "gugunNm": "제주시", "staNm": "A", "lat": 33, "lon": 126},
                    total_count=1,
                )
            )
        ]
    )
    client = AsyncKhoaClient(api_key="TEST_KEY", session=session, retries=0)

    pages = [
        page
        async for page in client.iter_oceans_beach_info_pages(
            sido_names=("제주",),
            num_of_rows=1,
        )
    ]

    assert pages[0].items[0].name == "A"
    assert session.calls[0]["url"].endswith("/OceansBeachInfoService1/getOceansBeachInfo1")


def test_constructor_strips_service_key_clipboard_whitespace(fake_client_factory):
    client, session = fake_client_factory(FakeResponse(khoa_payload([])))
    client_with_space = KhoaClient(
        api_key=" \n TEST_\r\nKEY \t",
        session=session,
        retries=0,
    )

    assert client_with_space.service_key == "TEST_KEY"
    client_with_space.fetch("vortex")
    assert session.calls[0]["params"]["serviceKey"] == "TEST_KEY"


def test_from_env_strips_primary_key_and_skips_blank_values(monkeypatch):
    monkeypatch.setenv("KHOA_SERVICE_KEY", " \n ")
    monkeypatch.setenv("KHOA_API_KEY", " \n ENV_\tKEY ")

    client = KhoaClient.from_env(retries=0)

    assert client.service_key == "ENV_KEY"


def test_constructor_loads_data_go_key_from_default_env_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KHOA_DATA_GO_KR_SERVICE_KEY", raising=False)
    monkeypatch.delenv("KHOA_SERVICE_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    monkeypatch.delenv("PUBLIC_DATA_SERVICE_KEY", raising=False)
    monkeypatch.delenv("KHOA_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "KHOA_DATA_GO_KR_SERVICE_KEY=' FILE_ KEY '\n",
        encoding="utf-8",
    )

    client = KhoaClient(retries=0)

    assert client.service_key == "FILE_KEY"


def test_service_key_loader_supports_source_specific_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("KHOA_DATA_GO_KR_SERVICE_KEY", raising=False)
    monkeypatch.delenv("KHOA_DIRECT_SERVICE_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KHOA_DATA_GO_KR_SERVICE_KEY=DATA_KEY\n"
        "KHOA_DIRECT_SERVICE_KEY= DIRECT_ KEY \n",
        encoding="utf-8",
    )

    assert get_service_key("data.go.kr", env_file=env_file) == "DATA_KEY"
    assert get_service_key("khoa.go.kr", env_file=env_file) == "DIRECT_KEY"


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

    result = client.beach_search("BCH001", service_key=" \nDIRECT_KEY\t")

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


def test_beach_search_prefers_khoa_direct_key_from_env_file(tmp_path, fake_client_factory):
    env_file = tmp_path / ".env"
    env_file.write_text("KHOA_DIRECT_SERVICE_KEY=DIRECT_KEY\n", encoding="utf-8")
    client, session = fake_client_factory(
        FakeResponse({"result": {"meta": {"beach_code": "BCH001"}, "data": []}})
    )

    result = client.beach_search("BCH001", env_file=env_file)

    assert result.id == "BCH001"
    assert session.calls[0]["params"]["ServiceKey"] == "DIRECT_KEY"


def test_oceans_beach_info_calls_public_data_endpoint_and_returns_dto(fake_client_factory):
    row = {
        "num": "1",
        "sidoNm": "제주",
        "gugunNm": "서귀포시",
        "staNm": "신양섭지코지",
        "beachWid": "80",
        "beachLen": "300",
        "beachKnd": "모래",
        "linkAddr": "https://www.visitjeju.net/",
        "linkNm": "제주관광",
        "beachImg": "https://cdn.example.com/beach.jpg",
        "linkTel": "동부보건소성산지소(064-782-2368)",
        "lat": "33.4348090000",
        "lon": "126.9230210000",
    }
    client, session = fake_client_factory(FakeResponse(_top_level_khoa_payload(row)))

    page = client.oceans_beach_info("제주", num_of_rows=1)

    call = session.calls[0]
    assert call["url"].endswith("/OceansBeachInfoService1/getOceansBeachInfo1")
    assert call["params"]["ServiceKey"] == "TEST_KEY"
    assert call["params"]["SIDO_NM"] == "제주"
    assert call["params"]["resultType"] == "JSON"
    item = page.items[0]
    assert isinstance(item, OceanBeachInfo)
    assert item.name == "신양섭지코지"
    assert item.source_key == "제주|서귀포시|신양섭지코지"
    assert item.coordinate is not None
    assert item.coordinate.lat == pytest.approx(33.434809)
    assert item.coordinate.lon == pytest.approx(126.923021)
    assert page.context is not None
    assert "ServiceKey" not in page.context.request_params


def test_oceans_beach_info_accepts_wrapped_live_payload(fake_client_factory):
    row = {
        "sidoNm": "충남",
        "gugunNm": "보령시",
        "staNm": "대천",
        "lat": "36.310000",
        "lon": "126.513000",
    }
    payload = {
        "getOceansBeachInfo": {
            "header": {"code": "00", "message": "NORMAL SERVICE"},
            "item": row,
            "numOfRows": 1,
            "pageNo": 1,
            "totalCount": 1,
        }
    }
    client, _session = fake_client_factory(FakeResponse(payload))

    page = client.oceans_beach_info("충남", num_of_rows=1)

    assert page.items[0].name == "대천"
    assert page.total_count == 1


def test_iter_oceans_beach_info_pages_scans_sido_pages(fake_client_factory):
    client, session = fake_client_factory(
        FakeResponse(
            _top_level_khoa_payload(
                [{"sidoNm": "제주", "gugunNm": "제주시", "staNm": "A", "lat": 33, "lon": 126}],
                page_no=1,
                num_of_rows=1,
                total_count=2,
            )
        ),
        FakeResponse(
            _top_level_khoa_payload(
                [{"sidoNm": "제주", "gugunNm": "제주시", "staNm": "B", "lat": 33, "lon": 126}],
                page_no=2,
                num_of_rows=1,
                total_count=2,
            )
        ),
        FakeResponse(_top_level_khoa_payload(None, result_code="03", total_count=0)),
    )

    pages = list(
        client.iter_oceans_beach_info_pages(
            sido_names=("제주", "부산"),
            num_of_rows=1,
        )
    )

    assert [page.items[0].name for page in pages] == ["A", "B"]
    assert [call["params"]["pageNo"] for call in session.calls] == [1, 2, 1]
    assert [call["params"]["SIDO_NM"] for call in session.calls] == ["제주", "제주", "부산"]


def test_api_catalog_contains_human_readable_dataset_names():
    catalog = get_api_catalog()
    roms = get_api_catalog_entry("roms")

    assert len(catalog) >= 46
    assert roms["service_key"] == "roms"
    assert roms["dataset_name"] == "ROMS 수치예측모델"
    assert roms["dataset_label"] == "ROMS 수치예측모델 (roms)"
    assert roms["data_source"] == "data.go.kr"
    assert roms["endpoint"] == "roms/GetRomsApiService"
    assert roms["service_key_url"].endswith("/15142227/openapi.do")
    assert "KHOA_DATA_GO_KR_SERVICE_KEY" in roms["service_key_env_names"]
    assert roms["required_params"] == ["ymin", "ymax", "xmin", "xmax"]


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
