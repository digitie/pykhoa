"""khoa가 발생시키는 예외."""

from __future__ import annotations


class KhoaError(Exception):
    """khoa 예외의 공통 기반 클래스."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "data.go.kr",
        endpoint: str | None = None,
        service: str | None = None,
        status_code: int | None = None,
        result_code: str | None = None,
        failure_kind: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.endpoint = endpoint
        self.service = service
        self.status_code = status_code
        self.result_code = result_code
        self.failure_kind = failure_kind
        self.retryable = retryable


class KhoaAuthError(KhoaError):
    """인증 실패 또는 serviceKey 누락 오류."""


class KhoaRateLimitError(KhoaError):
    """quota 또는 traffic limit 오류."""


class KhoaRequestError(KhoaError):
    """잘못된 요청 또는 파라미터 오류."""


class KhoaServerError(KhoaError):
    """상위 KHOA/data.go.kr 서버 오류."""


class KhoaParseError(KhoaError):
    """예상하지 못한 응답 형태 또는 파싱 오류."""


class KhoaNoDataError(KhoaError):
    """최소 한 개 item이 필요한 helper에서 발생하는 오류."""
