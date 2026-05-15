from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypedDict

from khoa import RomsPrediction, jsonable
from khoa.exceptions import KhoaParseError


class FixtureRunner(TypedDict):
    parse: Callable[[Mapping[str, Any]], Any]
    process: Callable[[Any], Any]


def parse_roms_response(body: Mapping[str, Any]) -> tuple[RomsPrediction, ...]:
    return tuple(RomsPrediction.from_raw(row) for row in _extract_items(body, service="roms"))


def process_model_items(parsed: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "count": len(parsed),
        "items": jsonable(parsed),
    }


RUNNERS: dict[str, FixtureRunner] = {
    "roms": {
        "parse": parse_roms_response,
        "process": process_model_items,
    },
}


def _extract_items(
    body: Mapping[str, Any],
    *,
    service: str,
) -> tuple[Mapping[str, Any], ...]:
    items = body.get("items")
    if items in (None, "", []):
        item_data = body.get("item")
    elif isinstance(items, Mapping):
        item_data = items.get("item")
    else:
        item_data = items
    if item_data in (None, "", []):
        return ()
    if isinstance(item_data, Mapping):
        return (item_data,)
    if isinstance(item_data, list) and all(isinstance(item, Mapping) for item in item_data):
        return tuple(item_data)
    raise KhoaParseError(
        "fixture response.body.items.item was not an object or list",
        service=service,
        failure_kind="parse",
    )
