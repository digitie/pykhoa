from __future__ import annotations

import json
from pathlib import Path

import pytest

from khoa import DebugRun, KhoaClient, Page, RomsPrediction
from khoa.debug import jsonable, redact_sensitive, save_fixture, slugify_case_name

from .conftest import FakeResponse, khoa_payload


def test_jsonable_converts_pydantic_models(fake_client_factory):
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
    payload = jsonable(page)

    assert payload["items"][0]["predicted_at"] == "2024-11-01T00:00:00+09:00"
    assert payload["items"][0]["water_temperature_c"] == 15.45


def test_redact_sensitive_masks_nested_values():
    payload = {
        "serviceKey": "SECRET",
        "headers": {"Authorization": "Bearer SECRET"},
        "items": [{"api_key": "SECRET"}, {"name": "safe"}],
    }

    assert redact_sensitive(payload) == {
        "serviceKey": "<REDACTED>",
        "headers": {"Authorization": "<REDACTED>"},
        "items": [{"api_key": "<REDACTED>"}, {"name": "safe"}],
    }


def test_save_fixture_writes_redacted_json_and_prevents_overwrite(tmp_path: Path):
    path = save_fixture(
        base_dir=tmp_path,
        function_name="roms",
        case_name="ROMS 정상 케이스",
        description="ROMS replay fixture",
        input_data={"api_key": "SECRET", "ymin": 34.0},
        request_data={"query": {"serviceKey": "SECRET"}},
        response_data={"status_code": 200, "body": {"items": []}},
        parsed_result=Page[RomsPrediction](items=()),
        processed_result={"count": 0},
        library_version="0.1.0",
    )

    assert path.name == "roms-정상-케이스.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["input"]["api_key"] == "<REDACTED>"
    assert saved["request"]["query"]["serviceKey"] == "<REDACTED>"
    assert saved["assertion"]["mode"] == "snapshot"

    with pytest.raises(FileExistsError):
        save_fixture(
            base_dir=tmp_path,
            function_name="roms",
            case_name="ROMS 정상 케이스",
            description="duplicate",
            input_data={},
            request_data={},
            response_data={},
            parsed_result={},
            processed_result={},
        )


def test_debug_fetch_returns_debug_run(fake_client_factory):
    row = {"predcDt": "2024-11-01 00:00:00", "lat": "34.01", "lot": "123.2"}
    client, _session = fake_client_factory(FakeResponse(khoa_payload(row)))

    run = client.debug_fetch(
        "roms",
        ymin=34.0,
        ymax=34.1,
        xmin=123.2,
        xmax=123.3,
    )

    assert isinstance(run, DebugRun)
    assert run.error is None
    assert run.request["method"] == "GET"
    assert "serviceKey" not in run.request["query"]
    assert run.response["status_code"] == 200
    assert run.processed == run.parsed.items
    assert run.catalog is not None
    assert run.catalog["dataset_name"] == "ROMS 수치예측모델"
    assert run.catalog["service_key_url"].endswith("/15142227/openapi.do")
    assert any("서비스키 신청 링크:" in item for item in run.trace)


def test_debug_fetch_captures_errors_without_raising(monkeypatch):
    monkeypatch.delenv("KHOA_SERVICE_KEY", raising=False)
    client = KhoaClient(api_key="TEST_KEY", retries=0)

    run = client.debug_fetch("dt_recent")

    assert run.error is not None
    assert run.error["type"] == "KhoaRequestError"
    assert run.catalog is not None
    assert run.catalog["dataset_name"] == "조위관측소 최신 관측데이터"
    assert run.parsed is None
    assert run.processed is None


def test_slugify_case_name_has_fallback():
    assert slugify_case_name("  테스트 Case 01  ") == "테스트-case-01"
    assert slugify_case_name("!!!") == "case"
