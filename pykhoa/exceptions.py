"""Exceptions raised by pykhoa."""

from __future__ import annotations


class KhoaError(Exception):
    """Base class for pykhoa errors."""

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
    """Authentication or missing service-key failure."""


class KhoaRateLimitError(KhoaError):
    """Quota or traffic-limit failure."""


class KhoaRequestError(KhoaError):
    """Invalid request or parameter failure."""


class KhoaServerError(KhoaError):
    """Upstream server failure."""


class KhoaParseError(KhoaError):
    """Unexpected response shape or parse failure."""


class KhoaNoDataError(KhoaError):
    """Raised by helpers that require at least one item."""
