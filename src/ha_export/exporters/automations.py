from __future__ import annotations

from pathlib import Path
from typing import List

from ha_export.exporters.base import BaseExporter, ExportItem


class AutomationsExporter(BaseExporter):
    """Exports automations via the Home Assistant REST API."""

    name = "automations"

    def discover(self) -> List[ExportItem]:
        api = self.context.api
        if api is None:
            raise RuntimeError("Automations exporter requires --ha-url and --token")

        items: List[ExportItem] = []
        records = api.list_automations()
        for record in records:
            automation_id = str(record.get("id") or record.get("entity_id"))
            automation = api.get_automation(automation_id)
            slug_source = automation.get("alias") or automation_id
            slug = self.slugify(str(slug_source))
            items.append(ExportItem(slug=slug, payload=automation, source=automation_id))
        return sorted(items, key=lambda item: item.slug)

    def export(self, item: ExportItem) -> str:
        payload = dict(item.payload)
        if "id" not in payload and item.source:
            payload["id"] = item.source
        return self.context.dump_yaml(payload)

    def output_path(self, item: ExportItem) -> Path:
        return Path("automations") / f"{item.slug}.yaml"
