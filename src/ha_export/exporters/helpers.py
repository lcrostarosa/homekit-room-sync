from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ha_export.exporters.base import BaseExporter, ExportItem
from ha_export.utils import fs


class HelpersExporter(BaseExporter):
    name = "helpers"

    def discover(self) -> List[ExportItem]:
        items: List[ExportItem] = []
        storage_dir = self.context.storage_dir

        for helper_file in fs.iter_storage_files(storage_dir, "input_"):
            helper_type = helper_file.name.replace(".storage", "")
            for entry in fs.storage_items(storage_dir, helper_file.name):
                entity_id = entry.get("entity_id") or entry.get("id") or helper_type
                slug = self.slugify(str(entity_id))
                payload = dict(entry)
                payload.setdefault("helper_type", helper_type)
                items.append(ExportItem(slug=slug, payload=payload, source=helper_file.name))

        return sorted(items, key=lambda item: item.slug)

    def export(self, item: ExportItem) -> str:
        payload: Dict[str, object] = dict(item.payload)
        payload.setdefault("id", item.payload.get("entity_id"))
        return self.context.dump_yaml(payload)

    def output_path(self, item: ExportItem) -> Path:
        return Path("helpers") / f"{item.slug}.yaml"
