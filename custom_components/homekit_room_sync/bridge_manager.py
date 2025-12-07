"""Bridge management helpers for HomeKit Room Sync."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ALLOWED_AREAS,
    CONF_BRIDGE_ID,
    CONF_BRIDGE_NAME,
    CONF_BRIDGE_TITLE,
    CONF_DEFAULT_ROOM,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITIES,
    CONF_MANAGED_BRIDGES,
)
from .coordinator import HomeKitRoomSyncCoordinator
from .storage import HomeKitStorageClient

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ManagedBridgeConfig:
    """In-memory representation of a HomeKit bridge configuration."""

    bridge_id: str
    friendly_name: str
    allowed_areas: set[str]
    include_entities: set[str]
    exclude_entities: set[str]
    default_room: str | None

    @property
    def title(self) -> str:
        """Return the human-friendly title."""
        return self.friendly_name or self.bridge_id

    def serialize(self) -> dict[str, object]:
        """Convert to dict suitable for ConfigEntry data."""
        return {
            CONF_BRIDGE_ID: self.bridge_id,
            CONF_BRIDGE_TITLE: self.friendly_name,
            CONF_ALLOWED_AREAS: sorted(self.allowed_areas),
            CONF_INCLUDE_ENTITIES: sorted(self.include_entities),
            CONF_EXCLUDE_ENTITIES: sorted(self.exclude_entities),
            CONF_DEFAULT_ROOM: self.default_room,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> ManagedBridgeConfig:
        """Create a config from stored data."""
        return cls(
            bridge_id=str(
                raw.get(CONF_BRIDGE_ID) or raw.get(CONF_BRIDGE_NAME) or ""
            ),
            friendly_name=str(raw.get(CONF_BRIDGE_TITLE) or raw.get(CONF_BRIDGE_NAME) or ""),
            allowed_areas=set(_coerce_str_list(raw.get(CONF_ALLOWED_AREAS))),
            include_entities=set(_coerce_str_list(raw.get(CONF_INCLUDE_ENTITIES))),
            exclude_entities=set(_coerce_str_list(raw.get(CONF_EXCLUDE_ENTITIES))),
            default_room=_coerce_optional_str(raw.get(CONF_DEFAULT_ROOM)),
        )


def _coerce_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, tuple):
        return [str(item) for item in value if isinstance(item, str)]
    return []


def _coerce_optional_str(value: object) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def parse_managed_bridge_configs(entry: ConfigEntry) -> list[ManagedBridgeConfig]:
    """Parse managed bridge configurations from a config entry."""
    configs: list[ManagedBridgeConfig] = []

    stored = entry.data.get(CONF_MANAGED_BRIDGES)
    if isinstance(stored, Iterable):
        for raw in stored:
            if isinstance(raw, dict):
                cfg = ManagedBridgeConfig.from_dict(raw)
                if cfg.bridge_id:
                    configs.append(cfg)
        return configs

    # Legacy single-bridge entries (version 1)
    legacy_bridge_id = entry.data.get(CONF_BRIDGE_NAME)
    if isinstance(legacy_bridge_id, str) and legacy_bridge_id:
        configs.append(
            ManagedBridgeConfig(
                bridge_id=legacy_bridge_id,
                friendly_name=entry.title or legacy_bridge_id,
                allowed_areas=set(_coerce_str_list(entry.data.get(CONF_ALLOWED_AREAS))),
                include_entities=set(),
                exclude_entities=set(),
                default_room=_coerce_optional_str(entry.data.get(CONF_DEFAULT_ROOM)),
            )
        )

    return configs


class HomeKitBridgeManager:
    """Manage multiple HomeKit Room Sync coordinators."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        bridge_configs: list[ManagedBridgeConfig],
    ) -> None:
        """Initialize the manager."""
        self._hass = hass
        self._entry = entry
        self._storage = HomeKitStorageClient(hass)
        self._coordinators: dict[str, HomeKitRoomSyncCoordinator] = {
            cfg.bridge_id: HomeKitRoomSyncCoordinator(
                hass,
                entry,
                cfg,
                self._storage,
            )
            for cfg in bridge_configs
        }

    @property
    def bridge_ids(self) -> list[str]:
        """Return the managed bridge IDs."""
        return list(self._coordinators.keys())

    def get_friendly_name(self, bridge_id: str) -> str:
        """Return the friendly name for a bridge ID."""
        coordinator = self._coordinators.get(bridge_id)
        if coordinator is None:
            return bridge_id
        return coordinator.config.title

    async def async_sync(self, bridge_id: str | None = None) -> bool:
        """Trigger synchronization."""
        if bridge_id:
            coordinator = self._coordinators.get(bridge_id)
            if not coordinator:
                _LOGGER.warning(
                    "Requested sync for unknown HomeKit bridge %s",
                    bridge_id,
                )
                return False
            return await coordinator.async_sync_rooms()

        if not self._coordinators:
            _LOGGER.debug("No HomeKit bridges configured for entry %s", self._entry.title)
            return True

        results = await asyncio.gather(
            *(coord.async_sync_rooms() for coord in self._coordinators.values()),
            return_exceptions=True,
        )

        success = True
        for bridge_id, result in zip(self._coordinators, results, strict=False):
            if isinstance(result, Exception):
                success = False
                _LOGGER.error(
                    "Sync failed for HomeKit bridge %s: %s",
                    bridge_id,
                    result,
                )
            elif result is False:
                success = False
        return success

    async def async_shutdown(self) -> None:
        """Cleanup resources when entry unloads."""
        self._coordinators.clear()

    @property
    def coordinators(self) -> dict[str, HomeKitRoomSyncCoordinator]:
        """Expose coordinators for testing."""
        return self._coordinators
