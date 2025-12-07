"""Coordinator for HomeKit Room Sync integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry,
    device_registry,
    entity_registry,
)

from .const import (
    HOMEKIT_DOMAIN,
    SERVICE_RELOAD,
    STORAGE_KEY_ACCESSORIES,
    STORAGE_KEY_ENTITY_ID,
    STORAGE_KEY_ROOM_NAME,
)
from .storage import HomeKitStorageClient

if TYPE_CHECKING:
    from .bridge_manager import ManagedBridgeConfig
    from homeassistant.helpers.area_registry import AreaRegistry
    from homeassistant.helpers.device_registry import DeviceRegistry
    from homeassistant.helpers.entity_registry import EntityRegistry

_LOGGER = logging.getLogger(__name__)


class HomeKitRoomSyncCoordinator:
    """Synchronize Home Assistant areas and HomeKit room assignments."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: ManagedBridgeConfig,
        storage: HomeKitStorageClient,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.config = config
        self._storage = storage
        self._state_path = storage.state_path(config.bridge_id)
        self._aids_path = storage.aids_path(config.bridge_id)
        self._iids_path = storage.iids_path(config.bridge_id)
        self._sync_lock = asyncio.Lock()

    @property
    def bridge_storage_file(self):
        """Return the primary storage path (legacy compatibility)."""
        return self._state_path

    async def async_sync_rooms(self) -> bool:
        """Synchronize HomeKit state."""
        async with self._sync_lock:
            return await self._perform_sync()

    async def _perform_sync(self) -> bool:
        if not await self._storage.exists(self._state_path):
            _LOGGER.warning(
                "HomeKit bridge storage file not found for %s (%s)",
                self.config.title,
                self._state_path,
            )
            return False

        aids_changes = await self._sync_allocations()

        storage_data = await self._storage.read(self._state_path)
        if storage_data is None:
            return False

        entity_reg = entity_registry.async_get(self.hass)
        device_reg = device_registry.async_get(self.hass)
        area_reg = area_registry.async_get(self.hass)

        accessories = storage_data.get("data", {}).get(
            STORAGE_KEY_ACCESSORIES,
            [],
        )

        if not isinstance(accessories, list):
            _LOGGER.warning(
                "Unexpected accessories structure for bridge %s",
                self.config.title,
            )
            return False

        updated_accessories: list[dict[str, Any]] = []
        removed_entities: list[str] = []
        changes_made = False

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

            include_override = entity_id in self.config.include_entities
            exclude_override = entity_id in self.config.exclude_entities

            if exclude_override:
                removed_entities.append(entity_id)
                changes_made = True
                _LOGGER.debug(
                    "Excluded %s from HomeKit bridge %s via override",
                    entity_id,
                    self.config.title,
                )
                continue

            if not self._should_include(area_id, include_override):
                removed_entities.append(entity_id)
                changes_made = True
                _LOGGER.debug(
                    "Removed %s; area %s not allowed for bridge %s",
                    entity_id,
                    area_id,
                    self.config.title,
                )
                continue

            room_name = resolved_room or self.config.default_room
            if include_override and not room_name:
                room_name = self.config.default_room

            current_room = accessory.get(STORAGE_KEY_ROOM_NAME)
            if room_name and room_name != current_room:
                accessory[STORAGE_KEY_ROOM_NAME] = room_name
                changes_made = True
                _LOGGER.debug(
                    "Updated room for %s on bridge %s: %s -> %s",
                    entity_id,
                    self.config.title,
                    current_room,
                    room_name,
                )

            updated_accessories.append(accessory)

        if removed_entities:
            storage_data["data"][STORAGE_KEY_ACCESSORIES] = updated_accessories
            _LOGGER.info(
                "Filtered %s accessories for bridge %s: %s",
                len(removed_entities),
                self.config.title,
                ", ".join(sorted(removed_entities)),
            )

        if changes_made:
            await self._storage.backup(self._state_path)
            if not await self._storage.write(self._state_path, storage_data):
                return False
            await self._reload_homekit()
            return True

        _LOGGER.debug(
            "No storage changes required for bridge %s",
            self.config.title,
        )
        return True if not aids_changes else await self._reload_after_alloc()

    def _should_include(self, area_id: str | None, include_override: bool) -> bool:
        """Return True if an entity should remain exposed."""
        if include_override:
            return True
        if not self.config.allowed_areas:
            return True
        return bool(area_id and area_id in self.config.allowed_areas)

    async def _reload_after_alloc(self) -> bool:
        try:
            await self._reload_homekit()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to reload HomeKit after allocation update for %s: %s",
                self.config.title,
                err,
            )
            return False
        return True

    async def _sync_allocations(self) -> bool:
        """Update aids/iids allocations when filters change."""
        if not self.config.allowed_areas:
            return False

        if not await self._storage.exists(self._aids_path):
            return False

        aids_data = await self._storage.read(self._aids_path)
        if aids_data is None:
            return False

        allocations: dict[str, int] = aids_data.get("data", {}).get(
            "allocations",
            {},
        )
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

            entity_id = entity_entry.entity_id if entity_entry else None
            if entity_id and entity_id in self.config.exclude_entities:
                removed[key] = aid
                continue
            if entity_id and entity_id in self.config.include_entities:
                kept[key] = aid
                continue

            area_id = None
            if entity_entry:
                area_id = entity_entry.area_id
                if not area_id and entity_entry.device_id:
                    device_entry = device_reg.async_get(entity_entry.device_id)
                    if device_entry:
                        area_id = device_entry.area_id

            if area_id and area_reg.async_get_area(area_id):
                if area_id in self.config.allowed_areas:
                    kept[key] = aid
                    continue

            removed[key] = aid

        if not removed:
            return False

        aids_data["data"]["allocations"] = kept
        await self._storage.backup(self._aids_path)
        if not await self._storage.write(self._aids_path, aids_data):
            return False

        if await self._storage.exists(self._iids_path):
            iids_data = await self._storage.read(self._iids_path)
            if iids_data and "data" in iids_data and "allocations" in iids_data["data"]:
                allocs = iids_data["data"]["allocations"]
                for aid in removed.values():
                    allocs.pop(str(aid), None)
                await self._storage.backup(self._iids_path)
                await self._storage.write(self._iids_path, iids_data)

        _LOGGER.info(
            "Pruned %s HomeKit allocations for bridge %s",
            len(removed),
            self.config.title,
        )
        await self._reload_homekit()
        return True

    def _resolve_area_and_room(
        self,
        entity_id: str,
        entity_reg: EntityRegistry,
        device_reg: DeviceRegistry,
        area_reg: AreaRegistry,
    ) -> tuple[str | None, str | None]:
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
        _area_id, room_name = self._resolve_area_and_room(
            entity_id,
            entity_reg,
            device_reg,
            area_reg,
        )
        return room_name or self.config.default_room

    async def _reload_homekit(self) -> None:
        try:
            await self.hass.services.async_call(
                HOMEKIT_DOMAIN,
                SERVICE_RELOAD,
                blocking=True,
            )
            _LOGGER.debug("Triggered HomeKit reload for %s", self.config.title)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to reload HomeKit for %s: %s", self.config.title, err)
