from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple, Type
import json
import logging

from ha_export import __version__
from ha_export.exporters.automations import AutomationsExporter
from ha_export.exporters.areas import AreasExporter
from ha_export.exporters.base import BaseExporter
from ha_export.exporters.dashboards import DashboardsExporter
from ha_export.exporters.entities import EntityRegistryExporter
from ha_export.exporters.helpers import HelpersExporter
from ha_export.exporters.lights import LightGroupsExporter
from ha_export.exporters.scenes import ScenesExporter
from ha_export.exporters.scripts import ScriptsExporter
from ha_export.models import ExportContext
from ha_export.utils import fs, yaml as yaml_utils
from ha_export.utils.api import HomeAssistantAPI

ExporterType = Type[BaseExporter]
EXPORTERS: Dict[str, ExporterType] = {
    "automations": AutomationsExporter,
    "scripts": ScriptsExporter,
    "scenes": ScenesExporter,
    "helpers": HelpersExporter,
    "entities": EntityRegistryExporter,
    "lights": LightGroupsExporter,
    "areas": AreasExporter,
    "dashboards": DashboardsExporter,
}


@dataclass(slots=True)
class RunResult:
    executed: Dict[str, int]


class ExportManager:
    def __init__(self, context: ExportContext) -> None:
        self.context = context

    def _resolve_exporters(self) -> Iterable[Tuple[str, ExporterType]]:
        requested = set(EXPORTERS.keys())
        if self.context.include:
            missing = self.context.include - requested
            if missing:
                raise ValueError(f"Unknown exporters requested: {', '.join(sorted(missing))}")
            requested &= self.context.include
        if self.context.exclude:
            requested -= self.context.exclude
        for name in sorted(requested):
            yield name, EXPORTERS[name]

    def run(self) -> RunResult:
        stats: Dict[str, int] = {}
        for name, exporter_cls in self._resolve_exporters():
            exporter = exporter_cls(self.context)
            try:
                items = exporter.discover()
            except Exception as exc:  # pragma: no cover - defensive
                self.context.logger.error("Failed to discover %s: %s", name, exc)
                continue
            changed = 0
            for item in items:
                rendered = exporter.export(item)
                output_path = self.context.output_dir / exporter.output_path(item)
                if fs.safe_write(
                    output_path,
                    rendered,
                    incremental=self.context.incremental,
                    dry_run=self.context.dry_run,
                    logger=self.context.logger,
                ):
                    changed += 1
            stats[name] = changed
        self._write_metadata()
        return RunResult(executed=stats)

    def _write_metadata(self) -> None:
        metadata_path = self.context.output_dir / "metadata.json"
        metadata = {
            "tool": "ha-config-exporter",
            "version": __version__,
            "config_source": str(self.context.config_dir.resolve()),
        }
        fs.safe_write(
            metadata_path,
            json.dumps(metadata, indent=2, sort_keys=True),
            incremental=self.context.incremental,
            dry_run=self.context.dry_run,
            logger=self.context.logger,
        )


def create_logger(verbose: bool, quiet: bool) -> logging.Logger:
    level = logging.INFO
    if verbose and not quiet:
        level = logging.DEBUG
    elif quiet and not verbose:
        level = logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s - %(message)s")
    return logging.getLogger("ha_export")


def build_context(
    *,
    ha_url: str | None,
    token: str | None,
    config_dir: Path,
    output_dir: Path,
    incremental: bool,
    dry_run: bool,
    include: set[str],
    exclude: set[str],
    logger: logging.Logger,
) -> ExportContext:
    api_client: HomeAssistantAPI | None = None
    if ha_url and token:
        api_client = HomeAssistantAPI(ha_url, token)
    storage_dir = config_dir / ".storage"
    fs.ensure_export_tree(output_dir)
    return ExportContext(
        config_dir=config_dir,
        storage_dir=storage_dir,
        output_dir=output_dir,
        api=api_client,
        incremental=incremental,
        dry_run=dry_run,
        include=include,
        exclude=exclude,
        logger=logger,
        dump_yaml=yaml_utils.dump_yaml,
    )


def run_export(
    *,
    ha_url: str | None,
    token: str | None,
    config_dir: str,
    output_dir: str,
    incremental: bool,
    dry_run: bool,
    include: Iterable[str] | None,
    exclude: Iterable[str] | None,
    verbose: bool,
    quiet: bool,
) -> RunResult:
    config_path = Path(config_dir).expanduser().resolve()
    output_path = Path(output_dir).expanduser().resolve()
    include_set = {name.lower() for name in include} if include else set()
    exclude_set = {name.lower() for name in exclude} if exclude else set()

    logger = create_logger(verbose, quiet)
    context = build_context(
        ha_url=ha_url,
        token=token,
        config_dir=config_path,
        output_dir=output_path,
        incremental=incremental,
        dry_run=dry_run,
        include=include_set,
        exclude=exclude_set,
        logger=logger,
    )
    manager = ExportManager(context)
    try:
        return manager.run()
    finally:
        if context.api:
            context.api.close()
