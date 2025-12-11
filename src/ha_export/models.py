from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import logging

from ha_export.utils.api import HomeAssistantAPI

YamlDumper = Callable[[object], str]


@dataclass(slots=True)
class ExportContext:
    """Container shared across exporters."""

    config_dir: Path
    storage_dir: Path
    output_dir: Path
    api: Optional[HomeAssistantAPI]
    incremental: bool
    dry_run: bool
    include: set[str]
    exclude: set[str]
    logger: logging.Logger
    dump_yaml: YamlDumper
