"""Coordinator for HomeKit Room Sync integration.

This module handles reading and writing HomeKit Bridge storage files,
mapping entity areas to HomeKit rooms, and triggering bridge reloads.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BRIDGE_NAME,
    CONF_DEFAULT_ROOM,
    HOMEKIT_DOMAIN,
    HOMEKIT_STORAGE_PREFIX,
    HOMEKIT_STORAGE_SUFFIX,
    SERVICE_RELOAD,
    STORAGE_KEY_ACCESSORIES,
    STORAGE_KEY_ENTITY_ID,
    STORAGE_KEY_ROOM_NAME,
)

if TYPE_CHECKING:
    from homeassistant.helpers.area_registry import AreaRegistry
    from homeassistant.helpers.device_registry import DeviceRegistry
    from homeassistant.helpers.entity_registry import EntityRegistry

_LOGGER = logging.getLogger(__name__)


class HomeKitRoomSyncCoordinator:
    """Coordinator class that manages HomeKit room synchronization.

    This coordinator reads HomeKit Bridge state files, determines the
    appropriate room for each exposed entity based on its Home Assistant
    area, and updates the storage files accordingly.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator.

        Args:
            hass: The Home Assistant instance.
            entry: The config entry for this integration.
        """
        self.hass = hass
        self.entry = entry
        self._bridge_name: str = entry.data[CONF_BRIDGE_NAME]
        self._default_room: str | None = entry.data.get(CONF_DEFAULT_ROOM)
        self._storage_path: Path = Path(hass.config.path(".storage"))
        self._sync_lock = asyncio.Lock()

    @property
    def bridge_storage_file(self) -> Path:
        """Get the path to the HomeKit bridge state file.

        Returns:
            Path to the bridge's state file in .storage directory.
        """
        filename = (
            f"{HOMEKIT_STORAGE_PREFIX}"
            f"{self._bridge_name}"
            f"{HOMEKIT_STORAGE_SUFFIX}"
        )
        return self._storage_path / filename

    async def async_sync_rooms(self) -> bool:
        """Synchronize Home Assistant areas to HomeKit rooms.

        This method reads the HomeKit bridge state file, updates room
        assignments based on entity areas, and writes the changes back.

        Returns:
            True if sync was successful, False otherwise.
        """
        async with self._sync_lock:
            return await self._perform_sync()

    async def _perform_sync(self) -> bool:
        """Perform the actual sync operation (internal, lock must be held).

        Returns:
            True if sync was successful, False otherwise.
        """
        storage_file = self.bridge_storage_file

        # Check if the storage file exists
        if not await self._file_exists(storage_file):
            _LOGGER.warning(
                "HomeKit bridge storage file not found: %s", storage_file
            )
            return False

        try:
            # Read the current storage data
            storage_data = await self._read_storage_file(storage_file)
            if storage_data is None:
                return False

            # Get registries for area lookups
            entity_registry = er.async_get(self.hass)
            device_registry = dr.async_get(self.hass)
            area_registry = ar.async_get(self.hass)

            # Track if any changes were made
            changes_made = False

            # Process accessories and update room assignments
            if STORAGE_KEY_ACCESSORIES in storage_data.get("data", {}):
                accessories = storage_data["data"][STORAGE_KEY_ACCESSORIES]
                for accessory in accessories:
                    entity_id = accessory.get(STORAGE_KEY_ENTITY_ID)
                    if not entity_id:
                        continue

                    # Determine the appropriate room for this entity
                    room_name = self._get_room_for_entity(
                        entity_id,
                        entity_registry,
                        device_registry,
                        area_registry,
                    )

                    # Update room if it changed
                    current_room = accessory.get(STORAGE_KEY_ROOM_NAME)
                    if room_name and room_name != current_room:
                        accessory[STORAGE_KEY_ROOM_NAME] = room_name
                        changes_made = True
                        _LOGGER.debug(
                            "Updated room for %s: %s -> %s",
                            entity_id,
                            current_room,
                            room_name,
                        )

            if changes_made:
                # Create backup before writing
                await self._create_backup(storage_file)

                # Write updated data
                if await self._write_storage_file(storage_file, storage_data):
                    _LOGGER.info(
                        "Successfully synced rooms for bridge: %s",
                        self._bridge_name,
                    )
                    # Trigger HomeKit reload
                    await self._reload_homekit()
                    return True
                return False

            _LOGGER.debug(
                "No room changes needed for bridge: %s", self._bridge_name
            )
            return True

        except Exception as err:
            _LOGGER.exception(
                "Error syncing rooms for bridge %s: %s",
                self._bridge_name,
                err,
            )
            return False

    def _get_room_for_entity(
        self,
        entity_id: str,
        entity_registry: EntityRegistry,
        device_registry: DeviceRegistry,
        area_registry: AreaRegistry,
    ) -> str | None:
        """Determine the HomeKit room name for an entity.

        The lookup priority is:
        1. Entity's directly assigned area
        2. Entity's device area
        3. Default room configured for this bridge

        Args:
            entity_id: The entity ID to look up.
            entity_registry: The entity registry.
            device_registry: The device registry.
            area_registry: The area registry.

        Returns:
            The room name, or None if no area could be determined.
        """
        # Try to get the entity entry
        entity_entry = entity_registry.async_get(entity_id)
        if entity_entry is None:
            return self._default_room

        area_id: str | None = None

        # Check entity's direct area assignment
        if entity_entry.area_id:
            area_id = entity_entry.area_id
        # Fall back to device's area
        elif entity_entry.device_id:
            device_entry = device_registry.async_get(entity_entry.device_id)
            if device_entry and device_entry.area_id:
                area_id = device_entry.area_id

        # Look up the area name
        if area_id:
            area_entry = area_registry.async_get_area(area_id)
            if area_entry:
                return area_entry.name

        # Fall back to default room
        return self._default_room

    async def _file_exists(self, path: Path) -> bool:
        """Check if a file exists asynchronously.

        Args:
            path: The path to check.

        Returns:
            True if the file exists, False otherwise.
        """
        return await self.hass.async_add_executor_job(path.exists)

    async def _read_storage_file(self, path: Path) -> dict[str, Any] | None:
        """Read and parse a JSON storage file.

        Args:
            path: The path to the storage file.

        Returns:
            Parsed JSON data, or None if reading failed.
        """
        try:
            content = await self.hass.async_add_executor_job(path.read_text)
            data = json.loads(content)

            # Validate basic structure
            if not isinstance(data, dict) or "data" not in data:
                _LOGGER.error("Invalid storage file structure: %s", path)
                return None

            return data
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to parse storage file %s: %s", path, err)
            return None
        except OSError as err:
            _LOGGER.error("Failed to read storage file %s: %s", path, err)
            return None

    async def _write_storage_file(
        self, path: Path, data: dict[str, Any]
    ) -> bool:
        """Write data to a storage file.

        Args:
            path: The path to write to.
            data: The data to write.

        Returns:
            True if writing succeeded, False otherwise.
        """
        try:
            content = json.dumps(data, indent=2, ensure_ascii=False)
            await self.hass.async_add_executor_job(path.write_text, content)
            return True
        except (OSError, TypeError) as err:
            _LOGGER.error("Failed to write storage file %s: %s", path, err)
            return False

    async def _create_backup(self, path: Path) -> bool:
        """Create a backup of the storage file before modification.

        Args:
            path: The path to the file to backup.

        Returns:
            True if backup succeeded, False otherwise.
        """
        backup_path = path.with_suffix(f"{path.suffix}.backup")
        try:
            await self.hass.async_add_executor_job(
                shutil.copy2, path, backup_path
            )
            _LOGGER.debug("Created backup: %s", backup_path)
            return True
        except OSError as err:
            _LOGGER.warning("Failed to create backup %s: %s", backup_path, err)
            return False

    async def _reload_homekit(self) -> None:
        """Trigger a HomeKit bridge reload to apply changes."""
        try:
            await self.hass.services.async_call(
                HOMEKIT_DOMAIN,
                SERVICE_RELOAD,
                blocking=True,
            )
            _LOGGER.debug("HomeKit reload triggered successfully")
        except Exception as err:
            _LOGGER.warning("Failed to reload HomeKit: %s", err)

    @classmethod
    def get_available_bridges(cls, hass: HomeAssistant) -> list[str]:
        """Get a list of available HomeKit bridges from storage.

        This method scans the .storage directory for HomeKit bridge
        state files and extracts their names.

        Args:
            hass: The Home Assistant instance.

        Returns:
            List of bridge names found in storage.
        """
        storage_path = Path(hass.config.path(".storage"))
        bridges: list[str] = []

        if not storage_path.exists():
            return bridges

        for file in storage_path.iterdir():
            if (
                file.is_file()
                and file.name.startswith(HOMEKIT_STORAGE_PREFIX)
                and file.name.endswith(HOMEKIT_STORAGE_SUFFIX)
            ):
                # Extract bridge name from filename
                # Format: homekit.{bridge_name}.state
                prefix_len = len(HOMEKIT_STORAGE_PREFIX)
                suffix_len = len(HOMEKIT_STORAGE_SUFFIX)
                name = file.name[prefix_len:-suffix_len]
                if name:
                    bridges.append(name)

        return sorted(bridges)
