from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from khoa import KhoaClient


class FakeResponse:
    def __init__(self, payload: Any, *, status_code: int = 200, text: str | None = None) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = text if text is not None else str(payload)

    def json(self) -> Any:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, params: Mapping[str, Any], timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        if not self.responses:
            raise AssertionError("no fake response left")
        return self.responses.pop(0)


def khoa_payload(
    item: Any,
    *,
    result_code: str = "0",
    result_msg: str = "NORMAL SERVICE",
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
        "response": {
            "header": {"resultCode": result_code, "resultMsg": result_msg},
            "body": body,
        }
    }


@pytest.fixture
def fake_client_factory():
    def factory(*responses: FakeResponse) -> tuple[KhoaClient, FakeSession]:
        session = FakeSession(list(responses))
        return KhoaClient("TEST_KEY", session=session, retries=0), session

    return factory
