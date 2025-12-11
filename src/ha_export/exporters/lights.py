from __future__ import annotations

from pathlib import Path
from typing import List

from ha_export.exporters.base import BaseExporter, ExportItem


class LightGroupsExporter(BaseExporter):
    name = "lights"

    def discover(self) -> List[ExportItem]:
        # Placeholder for future implementation
        return []

    def export(self, item: ExportItem) -> str:  # pragma: no cover - unreachable for now
        return self.context.dump_yaml(item.payload)

    def output_path(self, item: ExportItem) -> Path:  # pragma: no cover - unreachable for now
        return Path("lights") / f"{item.slug}.yaml"
