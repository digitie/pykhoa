from __future__ import annotations

import os

import pytest

from pykhoa import KhoaAuthError, KhoaClient, KhoaRateLimitError

pytestmark = pytest.mark.live

RUN_LIVE = os.getenv("PYKHOA_RUN_LIVE") == "1"


def live_client() -> KhoaClient:
    if not RUN_LIVE:
        pytest.skip("set PYKHOA_RUN_LIVE=1 to call real KHOA servers")
    key = os.getenv("KHOA_SERVICE_KEY")
    if not key:
        pytest.skip("KHOA_SERVICE_KEY is not set")
    return KhoaClient(key)


def test_live_vortex_smoke():
    client = live_client()

    try:
        page = client.fetch("vortex", num_of_rows=1)
    except (KhoaAuthError, KhoaRateLimitError) as exc:
        pytest.fail(f"live KHOA key was rejected: {exc}")

    assert page.context is not None
    assert page.context.endpoint == "vortex/GetVortexApiService"
    assert "serviceKey" not in page.context.request_params
    assert page.total_count >= 0


def test_live_roms_smoke():
    client = live_client()

    try:
        page = client.roms(ymin=34.0, ymax=34.1, xmin=123.2, xmax=123.3, num_of_rows=1)
    except (KhoaAuthError, KhoaRateLimitError) as exc:
        pytest.fail(f"live KHOA key was rejected: {exc}")

    assert page.context is not None
    assert page.context.endpoint == "roms/GetRomsApiService"
    assert page.total_count >= 0
