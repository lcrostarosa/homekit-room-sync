from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ha_export.exporters.base import BaseExporter, ExportItem
from ha_export.utils import fs


class ScriptsExporter(BaseExporter):
    name = "scripts"

    def discover(self) -> List[ExportItem]:
        scripts_path = self.context.config_dir / "scripts.yaml"
        yaml_payload = fs.read_yaml_file(scripts_path)
        items: List[ExportItem] = []

        if isinstance(yaml_payload, dict) and yaml_payload:
            for script_id in sorted(yaml_payload.keys()):
                body = self._normalize_script_body(script_id, yaml_payload[script_id])
                slug = self.slugify(script_id.replace("script.", ""))
                items.append(ExportItem(slug=slug, payload=body, source="scripts.yaml"))
            return items

        if isinstance(yaml_payload, list) and yaml_payload:
            for index, entry in enumerate(yaml_payload):
                alias = str(entry.get("alias", f"script-{index}"))
                slug = self.slugify(alias)
                body = self._normalize_script_body(alias, entry)
                items.append(ExportItem(slug=slug, payload=body, source="scripts.yaml"))
            return sorted(items, key=lambda item: item.slug)

        storage_items = self._scripts_from_storage()
        for entry in storage_items:
            slug_source = entry.get("alias") or entry.get("id") or "script"
            slug = self.slugify(str(slug_source))
            items.append(ExportItem(slug=slug, payload=entry, source=".storage"))
        return sorted(items, key=lambda item: item.slug)

    def export(self, item: ExportItem) -> str:
        return self.context.dump_yaml(item.payload)

    def output_path(self, item: ExportItem) -> Path:
        return Path("scripts") / f"{item.slug}.yaml"

    def _normalize_script_body(self, script_id: str, body: Any) -> Dict[str, Any]:
        if isinstance(body, dict):
            payload = dict(body)
        else:
            payload = {"sequence": body}
        entity_id = script_id if script_id.startswith("script.") else f"script.{script_id}"
        payload.setdefault("id", entity_id)
        payload.setdefault("alias", script_id.replace("script.", "").replace("_", " ").title())
        return payload

    def _scripts_from_storage(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for storage_file in fs.iter_storage_files(self.context.storage_dir, "script."):
            items.extend(fs.storage_items(self.context.storage_dir, storage_file.name))
        return items
