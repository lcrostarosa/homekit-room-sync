from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import difflib
import json

import yaml

EXPORT_FOLDERS = [
    "automations",
    "scripts",
    "scenes",
    "helpers",
    "lights",
    "entities",
    "areas",
    "dashboards",
]


def ensure_export_tree(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    for folder in EXPORT_FOLDERS:
        (base_dir / folder).mkdir(parents=True, exist_ok=True)


def read_yaml_file(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def read_storage_file(storage_dir: Path, name: str) -> Dict[str, Any]:
    path = storage_dir / name
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid JSON in {path}") from exc


def iter_storage_files(storage_dir: Path, prefix: str) -> Iterable[Path]:
    if not storage_dir.exists():
        return []
    return sorted(path for path in storage_dir.glob(f"{prefix}*"))


def storage_items(storage_dir: Path, name: str) -> List[Dict[str, Any]]:
    payload = read_storage_file(storage_dir, name)
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    items = data.get("items")
    if items is None:
        items = data.get("entities", [])
    return [item for item in items if isinstance(item, dict)]


def slugify(value: str) -> str:
    cleaned = (
        value.strip()
        .lower()
        .replace(" ", "-")
        .replace(".", "-")
        .replace("_", "-")
    )
    safe = [ch for ch in cleaned if ch.isalnum() or ch in {"-", "_"}]
    slug = "".join(safe) or "export"
    return slug


def safe_write(
    path: Path,
    content: str,
    *,
    incremental: bool,
    dry_run: bool,
    logger,
) -> bool:
    normalized = content.rstrip() + "\n"
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if incremental and existing == normalized:
        logger.debug("Skip unchanged %s", path)
        return False

    if dry_run:
        diff = difflib.unified_diff(
            (existing or "").splitlines(),
            normalized.splitlines(),
            fromfile=str(path),
            tofile=str(path),
            lineterm="",
        )
        diff_text = "\n".join(diff) or f"No changes for {path}"
        logger.info("[dry-run] %s", diff_text)
        return True

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8")
    logger.info("Wrote %s", path)
    return True
