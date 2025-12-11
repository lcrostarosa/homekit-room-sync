from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Callable, Optional

import pytest

from ha_export.models import ExportContext
from ha_export.utils import fs, yaml as yaml_utils

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(FIXTURES / "config", target)
    return target


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    target = tmp_path / "export"
    target.mkdir()
    fs.ensure_export_tree(target)
    return target


@pytest.fixture()
def logger() -> logging.Logger:
    logging.basicConfig(level=logging.DEBUG)
    return logging.getLogger("ha_export.tests")


@pytest.fixture()
def context_factory(config_dir: Path, output_dir: Path, logger: logging.Logger) -> Callable[..., ExportContext]:
    storage_dir = config_dir / ".storage"

    def _factory(*, api=None, incremental: bool = True, dry_run: bool = False) -> ExportContext:
        return ExportContext(
            config_dir=config_dir,
            storage_dir=storage_dir,
            output_dir=output_dir,
            api=api,
            incremental=incremental,
            dry_run=dry_run,
            include=set(),
            exclude=set(),
            logger=logger,
            dump_yaml=yaml_utils.dump_yaml,
        )

    return _factory


class MockHomeAssistantAPI:
    def __init__(self) -> None:
        data_path = FIXTURES / "api" / "automations.json"
        self._definition = json.loads(data_path.read_text(encoding="utf-8"))

    def list_automations(self):
        return self._definition.get("config", [])

    def get_automation(self, automation_id: str):
        detail_path = FIXTURES / "api" / f"automation_{automation_id}.json"
        if not detail_path.exists():
            raise KeyError(automation_id)
        return json.loads(detail_path.read_text(encoding="utf-8"))


@pytest.fixture()
def mock_api() -> MockHomeAssistantAPI:
    return MockHomeAssistantAPI()
