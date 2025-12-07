"""Storage helpers for interacting with HomeKit files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    HOMEKIT_AIDS_SUFFIX,
    HOMEKIT_DOMAIN,
    HOMEKIT_IIDS_SUFFIX,
    HOMEKIT_STORAGE_PREFIX,
    HOMEKIT_STORAGE_SUFFIX,
)

_LOGGER = logging.getLogger(__name__)


class HomeKitStorageClient:
    """Wrapper around Home Assistant's .storage directory."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the storage client."""
        self._hass = hass
        self._storage_path = Path(hass.config.path()) / ".storage"

    def state_path(self, bridge_id: str) -> Path:
        """Return the path to a bridge state file."""
        return self._storage_path / (
            f"{HOMEKIT_STORAGE_PREFIX}{bridge_id}{HOMEKIT_STORAGE_SUFFIX}"
        )

    def aids_path(self, bridge_id: str) -> Path:
        """Return the path to a bridge aids file."""
        return self._storage_path / (
            f"{HOMEKIT_STORAGE_PREFIX}{bridge_id}{HOMEKIT_AIDS_SUFFIX}"
        )

    def iids_path(self, bridge_id: str) -> Path:
        """Return the path to a bridge iids file."""
        return self._storage_path / (
            f"{HOMEKIT_STORAGE_PREFIX}{bridge_id}{HOMEKIT_IIDS_SUFFIX}"
        )

    async def exists(self, path: Path) -> bool:
        """Check if a path exists."""
        return bool(await self._hass.async_add_executor_job(path.exists))

    async def read(self, path: Path) -> dict[str, Any] | None:
        """Read and parse a JSON storage file."""
        try:
            content = await self._hass.async_add_executor_job(path.read_text)
        except OSError as err:
            _LOGGER.error("Failed to read storage file %s: %s", path, err)
            return None

        try:
            data = json.loads(content)
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to decode storage file %s: %s", path, err)
            return None

        if isinstance(data, dict) and "data" in data:
            return data
        if isinstance(data, dict):
            return {"data": data}

        _LOGGER.error("Unexpected structure in storage file %s", path)
        return None

    async def write(self, path: Path, data: dict[str, Any]) -> bool:
        """Write JSON data to storage."""
        try:
            content = json.dumps(data, indent=2, ensure_ascii=False)
            await self._hass.async_add_executor_job(path.write_text, content)
            return True
        except (OSError, TypeError) as err:
            _LOGGER.error("Failed to write storage file %s: %s", path, err)
            return False

    async def backup(self, path: Path) -> bool:
        """Create a backup of a storage file."""
        backup_path = path.with_suffix(f"{path.suffix}.backup")

        def _copy() -> bool:
            try:
                backup_path.write_text(path.read_text())
            except OSError as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to create backup %s: %s",
                    backup_path,
                    err,
                )
                return False
            return True

        return await self._hass.async_add_executor_job(_copy)

    def _extract_name_from_file(self, path: Path) -> str | None:
        """Try to derive a friendly name from a storage file."""
        try:
            content = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

        data = content.get("data", content) if isinstance(content, dict) else None
        if not isinstance(data, dict):
            return None

        for key in ("name", "bridge_name"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        for section in ("config", "bridge"):
            section_data = data.get(section)
            if isinstance(section_data, dict):
                name = section_data.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()

        return None

    def discover_bridges(self, fallback_names: dict[str, str]) -> dict[str, str]:
        """Discover HomeKit bridges present in storage."""
        bridges: dict[str, str] = {}

        if not self._storage_path.exists():
            return bridges

        for file in self._storage_path.iterdir():
            if (
                not file.is_file()
                or not file.name.startswith(HOMEKIT_STORAGE_PREFIX)
                or not file.name.endswith(HOMEKIT_STORAGE_SUFFIX)
            ):
                continue

            bridge_id = file.name[
                len(HOMEKIT_STORAGE_PREFIX) : -len(HOMEKIT_STORAGE_SUFFIX)
            ]
            if not bridge_id:
                continue

            friendly_name = self._extract_name_from_file(file)
            if not friendly_name:
                friendly_name = fallback_names.get(bridge_id)
            if not friendly_name:
                friendly_name = f"Bridge {bridge_id}"

            bridges[bridge_id] = friendly_name

        return bridges


async def async_discover_bridges(hass: HomeAssistant) -> dict[str, str]:
    """Discover HomeKit bridges with friendly names."""
    client = HomeKitStorageClient(hass)
    hk_entries = {
        entry.entry_id: entry.title or entry.data.get("name") or entry.entry_id
        for entry in hass.config_entries.async_entries(HOMEKIT_DOMAIN)
    }
    return await hass.async_add_executor_job(client.discover_bridges, hk_entries)
