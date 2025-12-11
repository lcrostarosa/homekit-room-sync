from __future__ import annotations

from pathlib import Path

import pytest

from ha_export.exporters.automations import AutomationsExporter
from ha_export.exporters.entities import EntityRegistryExporter
from ha_export.exporters.helpers import HelpersExporter
from ha_export.exporters.scenes import ScenesExporter
from ha_export.exporters.scripts import ScriptsExporter


def _render_first(exporter):
    items = exporter.discover()
    assert items, "Expected at least one export item"
    return items[0], exporter.export(items[0])


def test_scripts_exporter_uses_scripts_yaml(context_factory) -> None:
    exporter = ScriptsExporter(context_factory())
    item, content = _render_first(exporter)
    assert item.slug == "scene-launcher" or item.slug == "wake-up"
    assert "alias" in content
    assert "sequence" in content


def test_scenes_exporter_reads_storage(context_factory) -> None:
    exporter = ScenesExporter(context_factory())
    item, content = _render_first(exporter)
    assert item.slug == "relax"
    assert "entities" in content


def test_helpers_exporter_collects_all_helpers(context_factory) -> None:
    exporter = HelpersExporter(context_factory())
    items = exporter.discover()
    slugs = {item.slug for item in items}
    assert "input-boolean-guests" in slugs
    assert "input-select-modes" in slugs


def test_entity_registry_snapshot_deterministic(context_factory) -> None:
    exporter = EntityRegistryExporter(context_factory())
    item, content = _render_first(exporter)
    assert item.slug == "entities"
    assert "entities" in content
    assert "sensor.outdoor_temperature" in content


def test_automations_exporter_requires_api(context_factory) -> None:
    exporter = AutomationsExporter(context_factory())
    with pytest.raises(RuntimeError):
        exporter.discover()


def test_automations_exporter_uses_api(context_factory, mock_api) -> None:
    exporter = AutomationsExporter(context_factory(api=mock_api))
    items = exporter.discover()
    assert items[0].slug == "autonomous-light"
    content = exporter.export(items[0])
    assert "Autonomous Light" in content
