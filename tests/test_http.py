from __future__ import annotations

import pytest

from pykhoa import KhoaAuthError, KhoaParseError, KhoaRequestError

from .conftest import FakeResponse, khoa_payload


def test_http_status_auth_error(fake_client_factory):
    client, _session = fake_client_factory(
        FakeResponse({}, status_code=401, text="Unauthorized TEST_KEY")
    )

    with pytest.raises(KhoaAuthError, match=r"\[redacted\]"):
        client.fetch("vortex")


def test_non_json_xml_error_is_mapped(fake_client_factory):
    xml = """
    <OpenAPI_ServiceResponse>
      <cmmMsgHeader>
        <returnReasonCode>30</returnReasonCode>
        <returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>
      </cmmMsgHeader>
    </OpenAPI_ServiceResponse>
    """
    client, _session = fake_client_factory(FakeResponse(ValueError("bad json"), text=xml))

    with pytest.raises(KhoaAuthError):
        client.fetch("vortex")


def test_bad_envelope_raises_parse_error(fake_client_factory):
    client, _session = fake_client_factory(FakeResponse({"oops": {}}))

    with pytest.raises(KhoaParseError):
        client.fetch("vortex")


def test_result_code_request_error(fake_client_factory):
    client, _session = fake_client_factory(
        FakeResponse(khoa_payload(None, result_code="10", result_msg="bad"))
    )

    with pytest.raises(KhoaRequestError):
        client.fetch("vortex")
