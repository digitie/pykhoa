from __future__ import annotations

from datetime import date

import pytest

from pykhoa import KhoaClient, KhoaRequestError, RomsPrediction
from pykhoa.exceptions import KhoaAuthError, KhoaNoDataError

from .conftest import FakeResponse, khoa_payload


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
