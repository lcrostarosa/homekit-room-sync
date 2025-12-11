from __future__ import annotations

from pathlib import Path
from typing import List

from ha_export.exporters.base import BaseExporter, ExportItem


class AreasExporter(BaseExporter):
    name = "areas"

    def discover(self) -> List[ExportItem]:
        # Placeholder to keep directory populated without writes
        return []

    def export(self, item: ExportItem) -> str:  # pragma: no cover
        return self.context.dump_yaml(item.payload)

    def output_path(self, item: ExportItem) -> Path:  # pragma: no cover
        return Path("areas") / "structure.yaml"
