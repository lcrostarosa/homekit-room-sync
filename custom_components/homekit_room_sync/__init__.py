"""HomeKit Room Sync integration for Home Assistant.

This integration automatically synchronizes Home Assistant Areas
with HomeKit Room assignments for entities exposed through the
HomeKit Bridge integration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    EVENT_AREA_REGISTRY_UPDATED,
    EVENT_ENTITY_REGISTRY_UPDATED,
    SYNC_DEBOUNCE_DELAY,
)
from .coordinator import HomeKitRoomSyncCoordinator

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

    # Initialize the coordinator
    coordinator = HomeKitRoomSyncCoordinator(hass, entry)

    # Store coordinator and listener references for cleanup
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "listeners": [],
        "debounce_cancel": None,
    }

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
            await coordinator.async_sync_rooms()

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
    listeners.append(
        hass.bus.async_listen(EVENT_AREA_REGISTRY_UPDATED, schedule_sync)
    )
    _LOGGER.debug("Registered listener for %s", EVENT_AREA_REGISTRY_UPDATED)

    # Store listeners for cleanup
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data["listeners"] = listeners  # type: ignore[assignment]

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Perform initial sync
    _LOGGER.info("Performing initial room sync for bridge: %s", entry.title)
    await coordinator.async_sync_rooms()

    return True


async def async_update_options(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
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

    _LOGGER.info(
        "Successfully unloaded HomeKit Room Sync for bridge: %s", entry.title
    )
    return True


async def async_migrate_entry(
    _hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Migrate old entry to new version.

    This function handles config entry version migrations for
    backwards compatibility.

    Args:
        _hass: The Home Assistant instance (unused).
        entry: The config entry to migrate.

    Returns:
        True if migration was successful, False otherwise.
    """
    _LOGGER.debug("Migrating from version %s", entry.version)

    # Currently at version 1, no migration needed
    if entry.version == 1:
        return True

    _LOGGER.error("Migration from version %s is not supported", entry.version)
    return False
