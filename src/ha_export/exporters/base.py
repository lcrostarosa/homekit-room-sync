from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

from ha_export.models import ExportContext
from ha_export.utils import fs


@dataclass(slots=True)
class ExportItem:
    slug: str
    payload: Any
    source: str | None = None


class BaseExporter(ABC):
    """Common interface for export units."""

    name: str = "base"

    def __init__(self, context: ExportContext) -> None:
        self.context = context
        self.logger = context.logger

    @abstractmethod
    def discover(self) -> List[ExportItem]:
        """Return a deterministic list of export items."""

    @abstractmethod
    def export(self, item: ExportItem) -> str:
        """Render the export item as normalized YAML."""

    @abstractmethod
    def output_path(self, item: ExportItem) -> Path:
        """Return the relative output path for the item."""

    def slugify(self, value: str) -> str:
        return fs.slugify(value)

    def storage_items(self, name: str) -> list[dict[str, Any]]:
        return fs.storage_items(self.context.storage_dir, name)
