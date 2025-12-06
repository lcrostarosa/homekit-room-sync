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
from homeassistant.helpers import (
    area_registry,
    device_registry,
    entity_registry,
)

from .const import (
    CONF_BRIDGE_NAME,
    CONF_ALLOWED_AREAS,
    CONF_DEFAULT_ROOM,
    HOMEKIT_DOMAIN,
    HOMEKIT_AIDS_SUFFIX,
    HOMEKIT_IIDS_SUFFIX,
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
        self._allowed_areas: set[str] = set(
            entry.data.get(CONF_ALLOWED_AREAS, []) or []
        )
        self._storage_path: Path = Path(hass.config.path()) / ".storage"
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
                "HomeKit bridge storage file not found: %s",
                storage_file,
            )
            return False

        aids_changes = await self._sync_allocations()

        try:
            # Read the current storage data
            storage_data = await self._read_storage_file(storage_file)
            if storage_data is None:
                return False

            # Get registries for area lookups
            entity_reg = entity_registry.async_get(self.hass)
            device_reg = device_registry.async_get(self.hass)
            area_reg = area_registry.async_get(self.hass)

            # Track if any changes were made
            changes_made = False

            removed_entities: list[str] = []
            updated_accessories: list[dict[str, Any]] = []

            # Process accessories and update room assignments
            if STORAGE_KEY_ACCESSORIES in storage_data.get("data", {}):
                accessories = storage_data["data"][STORAGE_KEY_ACCESSORIES]
                for accessory in accessories:
                    entity_id = accessory.get(STORAGE_KEY_ENTITY_ID)
                    if not entity_id:
                        updated_accessories.append(accessory)
                        continue

                    area_id, resolved_room = self._resolve_area_and_room(
                        entity_id,
                        entity_reg,
                        device_reg,
                        area_reg,
                    )

                    if (
                        self._allowed_areas
                        and area_id not in self._allowed_areas
                    ):
                        removed_entities.append(entity_id)
                        changes_made = True
                        _LOGGER.debug(
                            "Skipping %s; area %s not allowed for bridge %s",
                            entity_id,
                            area_id,
                            self._bridge_name,
                        )
                        continue

                    room_name = resolved_room or self._default_room

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
                    updated_accessories.append(accessory)

            if removed_entities:
                storage_data["data"][STORAGE_KEY_ACCESSORIES] = (
                    updated_accessories
                )
                _LOGGER.info(
                    "Removed %s accessories outside allowed areas for %s: %s",
                    len(removed_entities),
                    self._bridge_name,
                    ", ".join(sorted(removed_entities)),
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
                "No room changes needed for bridge: %s",
                self._bridge_name,
            )
            return True if not aids_changes else await self._reload_after_alloc()

        except Exception as err:
            _LOGGER.exception(
                "Error syncing rooms for bridge %s: %s",
                self._bridge_name,
                err,
            )
            return False

    async def _reload_after_alloc(self) -> bool:
        """Reload HomeKit after allocation changes."""
        try:
            await self._reload_homekit()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to reload HomeKit after alloc update: %s", err)
            return False
        return True

    async def _sync_allocations(self) -> bool:
        """Synchronize HomeKit allocation files (.aids/.iids) with allowed areas."""
        if not self._allowed_areas:
            return False

        aids_path = self._storage_path / (
            f"{HOMEKIT_STORAGE_PREFIX}{self._bridge_name}{HOMEKIT_AIDS_SUFFIX}"
        )
        iids_path = self._storage_path / (
            f"{HOMEKIT_STORAGE_PREFIX}{self._bridge_name}{HOMEKIT_IIDS_SUFFIX}"
        )

        if not await self._file_exists(aids_path):
            return False

        aids_data = await self._read_storage_file(aids_path)
        if aids_data is None:
            return False

        allocations: dict[str, int] = aids_data.get("data", {}).get("allocations", {})
        if not allocations:
            return False

        entity_reg = entity_registry.async_get(self.hass)
        device_reg = device_registry.async_get(self.hass)
        area_reg = area_registry.async_get(self.hass)

        removed: dict[str, int] = {}
        kept: dict[str, int] = {}

        for key, aid in allocations.items():
            unique_id = key.split(".")[-1]
            entity_entry = next(
                (
                    entry
                    for entry in entity_reg.entities.values()
                    if entry.unique_id == unique_id
                ),
                None,
            )

            area_id = None
            if entity_entry:
                area_id = entity_entry.area_id
                if not area_id and entity_entry.device_id:
                    device_entry = device_reg.async_get(entity_entry.device_id)
                    if device_entry:
                        area_id = device_entry.area_id

            if area_id and area_reg.async_get_area(area_id):
                if area_id in self._allowed_areas:
                    kept[key] = aid
                    continue

            removed[key] = aid

        if not removed:
            return False

        aids_data["data"]["allocations"] = kept
        await self._create_backup(aids_path)
        if not await self._write_storage_file(aids_path, aids_data):
            return False

        if await self._file_exists(iids_path):
            iids_data = await self._read_storage_file(iids_path)
            if iids_data and "data" in iids_data and "allocations" in iids_data["data"]:
                allocs = iids_data["data"]["allocations"]
                for aid in removed.values():
                    allocs.pop(str(aid), None)
                await self._create_backup(iids_path)
                await self._write_storage_file(iids_path, iids_data)

        _LOGGER.info(
            "Removed %s allocations outside allowed areas for bridge %s",
            len(removed),
            self._bridge_name,
        )
        _LOGGER.debug("Removed allocations: %s", ", ".join(sorted(removed)))

        await self._reload_homekit()
        return True

    def _resolve_area_and_room(
        self,
        entity_id: str,
        entity_reg: EntityRegistry,
        device_reg: DeviceRegistry,
        area_reg: AreaRegistry,
    ) -> tuple[str | None, str | None]:
        """Resolve area_id and room name for an entity."""
        entity_entry = entity_reg.async_get(entity_id)
        if entity_entry is None:
            return None, None

        area_id: str | None = None

        if entity_entry.area_id:
            area_id = entity_entry.area_id
        elif entity_entry.device_id:
            device_entry = device_reg.async_get(entity_entry.device_id)
            if device_entry and device_entry.area_id:
                area_id = device_entry.area_id

        room_name: str | None = None
        if area_id:
            area_entry = area_reg.async_get_area(area_id)
            if area_entry:
                room_name = str(area_entry.name)

        return area_id, room_name

    def _get_room_for_entity(
        self,
        entity_id: str,
        entity_reg: EntityRegistry,
        device_reg: DeviceRegistry,
        area_reg: AreaRegistry,
    ) -> str | None:
        """Determine the HomeKit room name for an entity.

        The lookup priority is:
        1. Entity's directly assigned area
        2. Entity's device area
        3. Default room configured for this bridge

        Args:
            entity_id: The entity ID to look up.
            entity_reg: The entity registry.
            device_reg: The device registry.
            area_reg: The area registry.

        Returns:
            The room name, or None if no area could be determined.
        """
        _area_id, room_name = self._resolve_area_and_room(
            entity_id, entity_reg, device_reg, area_reg
        )
        if room_name:
            return room_name

        # Fall back to default room
        return self._default_room

    async def _file_exists(self, path: Path) -> bool:
        """Check if a file exists asynchronously.

        Args:
            path: The path to check.

        Returns:
            True if the file exists, False otherwise.
        """
        result = await self.hass.async_add_executor_job(path.exists)
        return bool(result)

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
            if not isinstance(data, dict):
                _LOGGER.error("Invalid storage file structure: %s", path)
                return None

            # Handle standard HA storage format (wrapped in "data")
            if "data" in data:
                return data

            # Handle flat format (no "data" wrapper)
            _LOGGER.debug("Storage missing 'data' key, wrapping: %s", path)
            return {"data": data}
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to parse storage file %s: %s", path, err)
            return None
        except OSError as err:
            _LOGGER.error("Failed to read storage file %s: %s", path, err)
            return None

    async def _write_storage_file(
        self,
        path: Path,
        data: dict[str, Any],
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
                shutil.copy2,
                path,
                backup_path,
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
    def get_available_bridges(cls, hass: HomeAssistant) -> dict[str, str]:
        """Get a map of available HomeKit bridges from storage.

        This method scans the .storage directory for HomeKit bridge
        state files and maps them to their friendly names from config entries.

        Args:
            hass: The Home Assistant instance.

        Returns:
            Dictionary mapping bridge ID to friendly name.
        """
        storage_path = Path(hass.config.path()) / ".storage"
        bridges: dict[str, str] = {}

        if not storage_path.exists():
            return bridges

        # Get all HomeKit config entries for name lookup
        hk_entries = {}
        for entry in hass.config_entries.async_entries(HOMEKIT_DOMAIN):
            # Prefer the UI title, then data["name"]
            name = entry.title or entry.data.get("name") or "Unknown Bridge"
            hk_entries[entry.entry_id] = name

        for file in storage_path.iterdir():
            if (
                file.is_file()
                and file.name.startswith(HOMEKIT_STORAGE_PREFIX)
                and file.name.endswith(HOMEKIT_STORAGE_SUFFIX)
            ):
                # Extract bridge ID from filename
                # Format: homekit.{entry_id}.state
                prefix_len = len(HOMEKIT_STORAGE_PREFIX)
                suffix_len = len(HOMEKIT_STORAGE_SUFFIX)
                entry_id = file.name[prefix_len:-suffix_len]

                if entry_id:
                    # Prefer name stored in the HomeKit state file
                    # (reflects renames inside HomeKit UI)
                    friendly_name = cls._extract_name_from_storage(file)

                    # Fallback to HomeKit config entry name
                    if not friendly_name:
                        friendly_name = hk_entries.get(entry_id)

                    # Final fallback to ID-based name
                    if not friendly_name:
                        friendly_name = f"Bridge {entry_id}"

                    bridges[entry_id] = friendly_name

        return bridges

    @staticmethod
    def _extract_name_from_storage(path: Path) -> str | None:
        """Try to read the bridge's friendly name from its storage file."""
        try:
            content = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

        data = (
            content.get("data", content)
            if isinstance(content, dict)
            else None
        )
        if isinstance(data, dict):
            config_section = (
                data.get("config")
                if isinstance(data.get("config"), dict)
                else {}
            )
            bridge_section = (
                data.get("bridge")
                if isinstance(data.get("bridge"), dict)
                else {}
            )
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    (
                        "HomeKit storage structure for %s: top_keys=%s, "
                        "data_keys=%s, config_keys=%s, bridge_keys=%s"
                    ),
                    path.name,
                    (
                        list(content.keys())
                        if isinstance(content, dict)
                        else "n/a"
                    ),
                    list(data.keys()),
                    list(config_section.keys()),
                    list(bridge_section.keys()),
                )
            name_candidates = [
                data.get("name"),
                data.get("bridge_name"),
                config_section.get("name"),
                bridge_section.get("name"),
            ]
            for name in name_candidates:
                if isinstance(name, str) and name.strip():
                    return name.strip()
        return None
