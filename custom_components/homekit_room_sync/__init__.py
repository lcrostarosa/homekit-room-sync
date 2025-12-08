"""HomeKit Room Sync integration for Home Assistant.

This integration automatically synchronizes Home Assistant Areas
with HomeKit Room assignments for entities exposed through the
HomeKit Bridge integration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .bridge_manager import HomeKitBridgeManager, parse_bridge_configs
from .const import (
    ATTR_BRIDGE_ID,
    ATTR_ENTRY_ID,
    CONF_AREAS,
    CONF_ALLOWED_AREAS,
    CONF_BRIDGES,
    CONF_BRIDGE_ID,
    CONF_BRIDGE_NAME,
    CONF_BRIDGE_TITLE,
    CONF_ENTRY_ID,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITIES,
    CONF_MANAGED_BRIDGES,
    DOMAIN,
    EVENT_AREA_REGISTRY_UPDATED,
    EVENT_DEVICE_REGISTRY_UPDATED,
    EVENT_ENTITY_REGISTRY_UPDATED,
    HOMEKIT_DOMAIN,
    SERVICE_SYNC,
    SYNC_DEBOUNCE_DELAY,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    # Type alias for unsubscribe callbacks
    UnsubscribeCallback = Callable[[], None]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomeKit Room Sync from a config entry.

    This function initializes the coordinator, registers event listeners
    for entity and area registry changes, and triggers an initial sync.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being set up.

    Returns:
        True if setup was successful, False otherwise.
    """
    _LOGGER.debug("Setting up HomeKit Room Sync for bridge: %s", entry.title)

    bridge_configs = parse_bridge_configs(entry)
    if not bridge_configs:
        _LOGGER.error(
            "No HomeKit bridges configured for %s. Please re-run the config flow.",
            entry.title or entry.entry_id,
        )
        return False

    manager = HomeKitBridgeManager(hass, entry, bridge_configs)

    # Store coordinator and listener references for cleanup
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "manager": manager,
        "listeners": [],
        "debounce_cancel": None,
    }

    # Register manual sync service once
    if not hass.data[DOMAIN].get("service_registered"):

        async def async_handle_manual_sync(call) -> None:
            """Manually trigger a sync for one or all bridges."""
            entry_id = call.data.get(ATTR_ENTRY_ID)
            bridge_id = call.data.get(ATTR_BRIDGE_ID)

            async def _sync_target(manager: HomeKitBridgeManager) -> None:
                if bridge_id:
                    if bridge_id in manager.bridge_ids:
                        await manager.async_sync(bridge_id)
                    return
                await manager.async_sync()

            domain_data = hass.data.get(DOMAIN, {})
            if entry_id:
                entry_data = domain_data.get(entry_id)
                if not entry_data:
                    _LOGGER.warning(
                        "Manual sync requested for unknown entry_id: %s",
                        entry_id,
                    )
                    return
                await _sync_target(entry_data["manager"])
                return

            tasks = [
                _sync_target(entry_data["manager"])
                for key, entry_data in domain_data.items()
                if key != "service_registered"
            ]
            if tasks:
                await asyncio.gather(*tasks)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SYNC,
            async_handle_manual_sync,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_ENTRY_ID): str,
                    vol.Optional(ATTR_BRIDGE_ID): str,
                }
            ),
        )
        hass.data[DOMAIN]["service_registered"] = True
        _LOGGER.debug("Registered manual sync service: %s.%s", DOMAIN, SERVICE_SYNC)

    # Set up the debounced sync function
    @callback
    def schedule_sync(_event: Event | None = None) -> None:
        """Schedule a debounced room sync.

        This callback is triggered by entity or area registry events.
        It uses debouncing to batch rapid changes into a single sync
        operation, preventing excessive HomeKit reloads.

        Args:
            _event: The event that triggered this callback (unused).
        """
        entry_data = hass.data[DOMAIN].get(entry.entry_id)
        if entry_data is None:
            return

        # Cancel any pending sync
        if entry_data["debounce_cancel"] is not None:
            entry_data["debounce_cancel"]()
            entry_data["debounce_cancel"] = None

        async def perform_sync(_now: object) -> None:
            """Execute the actual sync after debounce delay."""
            entry_data = hass.data[DOMAIN].get(entry.entry_id)
            if entry_data is None:
                return

            entry_data["debounce_cancel"] = None
            await manager.async_sync()

        # Schedule new sync with debounce delay
        entry_data["debounce_cancel"] = async_call_later(
            hass, SYNC_DEBOUNCE_DELAY, perform_sync
        )

    # Register event listeners
    listeners: list[UnsubscribeCallback] = []

    # Listen for entity registry updates
    listeners.append(
        hass.bus.async_listen(EVENT_ENTITY_REGISTRY_UPDATED, schedule_sync)
    )
    _LOGGER.debug("Registered listener for %s", EVENT_ENTITY_REGISTRY_UPDATED)

    # Listen for area registry updates
    listeners.append(hass.bus.async_listen(EVENT_AREA_REGISTRY_UPDATED, schedule_sync))
    _LOGGER.debug("Registered listener for %s", EVENT_AREA_REGISTRY_UPDATED)

    listeners.append(
        hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, schedule_sync)
    )
    _LOGGER.debug("Registered listener for %s", EVENT_DEVICE_REGISTRY_UPDATED)

    # Store listeners for cleanup
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data["listeners"] = listeners  # type: ignore[assignment]

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Perform initial sync
    _LOGGER.info("Performing initial room sync for bridge: %s", entry.title)
    await manager.async_sync()

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.

    When options are changed through the UI, reload the integration
    to apply the new settings.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry that was updated.
    """
    _LOGGER.debug("Options updated, reloading integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    This function cleans up event listeners and removes stored data
    when the integration is unloaded.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being unloaded.

    Returns:
        True if unload was successful, False otherwise.
    """
    _LOGGER.debug("Unloading HomeKit Room Sync for bridge: %s", entry.title)

    entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if entry_data is None:
        return True

    # Cancel any pending debounced sync
    if entry_data.get("debounce_cancel") is not None:
        entry_data["debounce_cancel"]()

    # Remove event listeners
    for unsub in entry_data.get("listeners", []):
        unsub()

    await entry_data["manager"].async_shutdown()

    _LOGGER.info("Successfully unloaded HomeKit Room Sync for entry: %s", entry.title)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle config entry migrations."""
    _LOGGER.debug(
        "Migrating HomeKit Room Sync entry %s from version %s",
        entry.entry_id,
        entry.version,
    )

    if entry.version == 2:
        return await _migrate_v2_to_v3(hass, entry)

    if entry.version == 3:
        return True

    _LOGGER.error("Migration from version %s is not supported", entry.version)
    return False


async def _migrate_v2_to_v3(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    raw_bridges = entry.data.get(CONF_MANAGED_BRIDGES)
    if not isinstance(raw_bridges, list):
        _LOGGER.error("Entry %s missing managed bridges", entry.entry_id)
        return False

    homekit_entries = hass.config_entries.async_entries(HOMEKIT_DOMAIN)
    lookup_by_id = {hk.entry_id: hk.entry_id for hk in homekit_entries}
    lookup_by_title = {
        (hk.title or "").strip(): hk.entry_id for hk in homekit_entries if hk.title
    }
    lookup_by_name = {
        str(hk.data.get("name")).strip(): hk.entry_id
        for hk in homekit_entries
        if isinstance(hk.data.get("name"), str)
    }

    def resolve_entry_id(identifier: str) -> str | None:
        if identifier in lookup_by_id:
            return identifier
        if identifier in lookup_by_title:
            return lookup_by_title[identifier]
        if identifier in lookup_by_name:
            return lookup_by_name[identifier]
        return None

    bridges: list[dict[str, object]] = []
    unknown: list[str] = []

    for raw in raw_bridges:
        if not isinstance(raw, dict):
            continue
        identifier = str(
            raw.get(CONF_BRIDGE_ID)
            or raw.get(CONF_BRIDGE_TITLE)
            or raw.get(CONF_BRIDGE_NAME)
            or ""
        ).strip()
        resolved = resolve_entry_id(identifier)
        if not resolved:
            unknown.append(identifier or "<unknown>")
            continue

        bridges.append(
            {
                CONF_ENTRY_ID: resolved,
                CONF_AREAS: list(raw.get(CONF_ALLOWED_AREAS, [])),
                CONF_INCLUDE_ENTITIES: list(raw.get(CONF_INCLUDE_ENTITIES, [])),
                CONF_EXCLUDE_ENTITIES: list(raw.get(CONF_EXCLUDE_ENTITIES, [])),
            }
        )

    if not bridges:
        _LOGGER.error(
            "Unable to migrate entry %s: no HomeKit bridges resolved (%s)",
            entry.entry_id,
            ", ".join(unknown) or "no identifiers provided",
        )
        return False

    entry.version = 3
    data = {CONF_BRIDGES: bridges}
    hass.config_entries.async_update_entry(entry, data=data)
    entry.data = data

    if unknown:
        _LOGGER.warning(
            "Skipped %s HomeKit bridge(s) during migration for entry %s: %s",
            len(unknown),
            entry.entry_id,
            ", ".join(unknown),
        )
    _LOGGER.info("Migrated HomeKit Room Sync entry %s to version 3", entry.entry_id)
    return True
