from __future__ import annotations

from ha_export.utils import yaml as yaml_utils


def test_yaml_normalization_orders_keys_and_drops_nulls() -> None:
    payload = {
        "action": [{"service": "light.turn_on", "data": None}],
        "alias": "Sample",
        "description": None,
        "trigger": [{"platform": "time", "at": "07:00"}],
        "context": {"foo": "bar"},
    }
    rendered = yaml_utils.dump_yaml(payload)
    assert rendered.startswith("alias") or rendered.startswith("id")
    assert "context" not in rendered
    assert "null" not in rendered
