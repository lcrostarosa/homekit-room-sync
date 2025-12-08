"""Coordinator for HomeKit Room Sync integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .exposure import ExposurePlan, build_exposure_plan

if TYPE_CHECKING:  # pragma: no cover
    from homeassistant.config_entries import ConfigEntry as HACoreConfigEntry

    from .bridge_manager import ManagedBridgeConfig


_LOGGER = logging.getLogger(__name__)


class HomeKitRoomSyncCoordinator:
    """Synchronize Home Assistant area filters with a HomeKit bridge."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: "ManagedBridgeConfig",
        _storage_client: Any | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.config = config
        self._sync_lock = asyncio.Lock()

    async def async_sync_rooms(self) -> bool:
        """Run a synchronization cycle for this bridge."""
        async with self._sync_lock:
            return await self._perform_sync()

    async def _perform_sync(self) -> bool:
        homekit_entry = self._get_homekit_entry()
        if homekit_entry is None:
            _LOGGER.warning(
                "HomeKit bridge %s (%s) not found; skipping sync",
                self.config.title,
                self.config.bridge_id,
            )
            return False

        plan = build_exposure_plan(self.hass, self.config)
        if not plan.allowed_entities:
            _LOGGER.warning(
                "HomeKit bridge %s currently has no entities to expose using the configured filters",
                self.config.title,
            )

        if not self._apply_plan(homekit_entry, plan):
            _LOGGER.debug("No HomeKit filter changes required for %s", self.config.title)
            return True

        await self.hass.config_entries.async_reload(homekit_entry.entry_id)
        self._log_preview(plan)
        return True

    def _get_homekit_entry(self) -> "HACoreConfigEntry | None":
        return self.hass.config_entries.async_get_entry(self.config.bridge_id)

    def _apply_plan(
        self,
        homekit_entry: "HACoreConfigEntry",
        plan: ExposurePlan,
    ) -> bool:
        current_data = dict(homekit_entry.data)
        new_filter = self._build_filter(current_data.get("filter"), plan)
        new_entity_config = self._build_entity_config(
            current_data.get("entity_config"),
            plan,
        )

        changed = False
        if not _dicts_equal(new_filter, current_data.get("filter")):
            current_data["filter"] = new_filter
            changed = True

        if not _dicts_equal(new_entity_config, current_data.get("entity_config")):
            current_data["entity_config"] = new_entity_config
            changed = True

        if not changed:
            return False

        self.hass.config_entries.async_update_entry(homekit_entry, data=current_data)
        return True

    def _build_filter(
        self,
        existing: dict[str, Any] | None,
        plan: ExposurePlan,
    ) -> dict[str, Any]:
        result = dict(existing or {})
        result["include_entities"] = plan.include_entities
        result["exclude_entities"] = plan.exclude_entities
        result["include_areas"] = sorted(self.config.allowed_areas)
        return result

    def _build_entity_config(
        self,
        existing: dict[str, Any] | None,
        plan: ExposurePlan,
    ) -> dict[str, Any]:
        existing = existing or {}
        new_config: dict[str, Any] = {}

        for entity_id in plan.allowed_entities:
            config = dict(existing.get(entity_id, {}))
            room = plan.rooms_by_entity.get(entity_id)
            if room:
                config["room"] = room
            elif "room" in config:
                config.pop("room")

            if config:
                new_config[entity_id] = config

        return new_config

    def _log_preview(self, plan: ExposurePlan) -> None:
        if not plan.include_entities:
            _LOGGER.info("Bridge %s currently exposes no entities", self.config.title)
            return

        preview = ", ".join(plan.include_entities[:10])
        if len(plan.include_entities) > 10:
            preview = f"{preview}, …"

        _LOGGER.info(
            "Bridge %s will expose %d entities (%s)",
            self.config.title,
            len(plan.include_entities),
            preview,
        )


def _dicts_equal(first: Any | None, second: Any | None) -> bool:
    if first is None and second is None:
        return True
    if first is None or second is None:
        return False
    return dict(first) == dict(second)
