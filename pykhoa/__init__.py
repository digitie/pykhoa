"""Python helpers for KHOA ODMI OpenAPI services."""

from .client import KhoaClient, KhoaODMIClient
from .exceptions import (
    KhoaAuthError,
    KhoaError,
    KhoaNoDataError,
    KhoaParseError,
    KhoaRateLimitError,
    KhoaRequestError,
    KhoaServerError,
)
from .models import Page, RawRecord, ResponseContext, RomsPrediction
from .services import (
    DEFAULT_BASE_URL,
    KHOA_ODMI_LIST_URL,
    SERVICE_BY_KEY,
    SERVICE_DEFINITIONS,
    ServiceDefinition,
    get_service,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "KHOA_ODMI_LIST_URL",
    "SERVICE_BY_KEY",
    "SERVICE_DEFINITIONS",
    "KhoaAuthError",
    "KhoaClient",
    "KhoaError",
    "KhoaNoDataError",
    "KhoaODMIClient",
    "KhoaParseError",
    "KhoaRateLimitError",
    "KhoaRequestError",
    "KhoaServerError",
    "Page",
    "RawRecord",
    "ResponseContext",
    "RomsPrediction",
    "ServiceDefinition",
    "get_service",
]
