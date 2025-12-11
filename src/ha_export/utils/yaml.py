from __future__ import annotations

from typing import Any

import yaml

PRIORITY_KEYS = ["id", "alias", "description", "trigger", "condition", "action", "mode"]
DROP_KEYS = {
    "metadata",
    "ui_metadata",
    "trace",
    "trace_timestamp",
    "last_triggered",
    "editable",
    "source",
    "raw_config",
    "context",
    "created_at",
    "modified",
}


def _should_drop(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)) and not value:
        return True
    if isinstance(value, dict) and not value:
        return True
    return False


def _normalize_mapping(data: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}

    for key in PRIORITY_KEYS:
        if key in data:
            value = normalize(data[key])
            if not _should_drop(value):
                ordered[key] = value

    remaining_keys = sorted(
        key for key in data.keys() if key not in PRIORITY_KEYS and key not in DROP_KEYS
    )
    for key in remaining_keys:
        value = normalize(data[key])
        if not _should_drop(value):
            ordered[key] = value

    return ordered


def normalize(data: Any) -> Any:
    if isinstance(data, dict):
        return _normalize_mapping(data)
    if isinstance(data, list):
        normalized_items = [normalize(item) for item in data]
        return [item for item in normalized_items if not _should_drop(item)]
    return data


def dump_yaml(data: Any) -> str:
    normalized = normalize(data)
    rendered = yaml.safe_dump(
        normalized,
        indent=2,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=False,
    )
    return rendered.rstrip() + "\n"
