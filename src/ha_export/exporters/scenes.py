from __future__ import annotations

from pathlib import Path
from typing import List

from ha_export.exporters.base import BaseExporter, ExportItem


class ScenesExporter(BaseExporter):
    name = "scenes"

    def discover(self) -> List[ExportItem]:
        items: List[ExportItem] = []
        for entry in self.storage_items("scene.storage"):
            slug_source = entry.get("alias") or entry.get("name") or entry.get("id") or "scene"
            slug = self.slugify(str(slug_source))
            payload = dict(entry)
            payload.setdefault("id", entry.get("id"))
            items.append(ExportItem(slug=slug, payload=payload, source="scene.storage"))
        return sorted(items, key=lambda item: item.slug)

    def export(self, item: ExportItem) -> str:
        return self.context.dump_yaml(item.payload)

    def output_path(self, item: ExportItem) -> Path:
        return Path("scenes") / f"{item.slug}.yaml"
