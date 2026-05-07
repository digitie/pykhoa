"""Pydantic response models returned by pykhoa."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ._convert import to_datetime_or_none, to_float_or_none

T = TypeVar("T")
RawRecord = Mapping[str, Any]


class KhoaModel(BaseModel):
    """Base immutable model for pykhoa."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ResponseContext(KhoaModel):
    """Metadata about a KHOA API call, without exposing the service key."""

    provider: str = "data.go.kr"
    service_key: str
    service_title: str
    service_path: str
    operation: str
    endpoint: str
    request_url: str
    request_params: dict[str, Any] = Field(default_factory=dict)
    collected_at: datetime


class Page(KhoaModel, Generic[T]):
    """One paginated KHOA response page."""

    items: tuple[T, ...]
    total_count: int = 0
    page_no: int = 1
    num_of_rows: int = 10
    raw: dict[str, Any] = Field(default_factory=dict)
    context: ResponseContext | None = None

    @property
    def has_next_page(self) -> bool:
        return self.page_no * self.num_of_rows < self.total_count

    @property
    def next_page_no(self) -> int | None:
        return self.page_no + 1 if self.has_next_page else None

    @property
    def endpoint(self) -> str | None:
        return self.context.endpoint if self.context else None

    @property
    def request_params(self) -> dict[str, Any]:
        return dict(self.context.request_params) if self.context else {}


class RomsPrediction(KhoaModel):
    """Typed row for the ROMS numerical prediction endpoint."""

    predicted_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    current_direction_deg: float | None = None
    current_speed_cm_s: float | None = None
    water_temperature_c: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, row: Mapping[str, Any]) -> RomsPrediction:
        return cls(
            predicted_at=to_datetime_or_none(row.get("predcDt")),
            latitude=to_float_or_none(row.get("lat")),
            longitude=to_float_or_none(row.get("lot")),
            current_direction_deg=to_float_or_none(row.get("crdir")),
            current_speed_cm_s=to_float_or_none(row.get("crsp")),
            water_temperature_c=to_float_or_none(row.get("wtem")),
            raw=dict(row),
        )
