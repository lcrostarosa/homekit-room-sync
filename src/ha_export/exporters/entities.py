from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ha_export.exporters.base import BaseExporter, ExportItem

_KEEP_KEYS = [
    "entity_id",
    "name",
    "original_name",
    "platform",
    "device_id",
    "area_id",
    "disabled_by",
]


class EntityRegistryExporter(BaseExporter):
    name = "entities"

    def discover(self) -> List[ExportItem]:
        entries = []
        for item in self.storage_items("core.entity_registry"):
            cleaned: Dict[str, str] = {}
            for key in _KEEP_KEYS:
                value = item.get(key)
                if value not in (None, ""):
                    cleaned[key] = value
            if cleaned:
                entries.append(cleaned)
        entries.sort(key=lambda entry: entry.get("entity_id", ""))
        payload = {"entities": entries}
        return [ExportItem(slug="entities", payload=payload, source="core.entity_registry")]

    def export(self, item: ExportItem) -> str:
        return self.context.dump_yaml(item.payload)

    def output_path(self, item: ExportItem) -> Path:
        return Path("entities") / "entities.yaml"
