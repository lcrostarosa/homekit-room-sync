"""Pytest fixtures for HomeKit Room Sync tests."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Inject mock homeassistant modules before importing custom_components
from tests.ha_mocks import homeassistant
from tests.ha_mocks.homeassistant import config_entries, core
from tests.ha_mocks.homeassistant.helpers import (
    area_registry,
    device_registry,
    entity_registry,
    event,
)

sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.config_entries"] = config_entries
sys.modules["homeassistant.helpers"] = homeassistant.helpers
sys.modules["homeassistant.helpers.area_registry"] = area_registry
sys.modules["homeassistant.helpers.device_registry"] = device_registry
sys.modules["homeassistant.helpers.entity_registry"] = entity_registry
sys.modules["homeassistant.helpers.event"] = event

from custom_components.homekit_room_sync.const import (
    CONF_ALLOWED_AREAS,
    CONF_BRIDGE_ID,
    CONF_BRIDGE_TITLE,
    CONF_DEFAULT_ROOM,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITIES,
    CONF_MANAGED_BRIDGES,
)


@pytest.fixture
def mock_homekit_entry() -> MagicMock:
    """Create a mock HomeKit config entry."""
    entry = MagicMock()
    entry.entry_id = "test_bridge"
    entry.domain = "homekit"
    entry.title = "Test HomeKit Bridge"
    entry.data = {"filter": {}, "entity_config": {}}
    entry.options = {}
    return entry


@pytest.fixture
def mock_hass(mock_homekit_entry: MagicMock) -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path = MagicMock(return_value="/config")
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock(return_value=MagicMock())
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.services.async_register = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    hass.config_entries.async_get_entry = MagicMock(return_value=mock_homekit_entry)

    def _update_entry(entry, data=None, options=None):
        if entry is mock_homekit_entry and data is not None:
            mock_homekit_entry.data = data

    hass.config_entries.async_update_entry = MagicMock(side_effect=_update_entry)
    hass.config_entries.async_entries = MagicMock(return_value=[mock_homekit_entry])

    # Mock async_add_executor_job to run synchronously
    async def mock_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs)

    hass.async_add_executor_job = mock_executor_job
    return hass


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_MANAGED_BRIDGES: [
            {
                CONF_BRIDGE_ID: "test_bridge",
                CONF_BRIDGE_TITLE: "Test Bridge",
                CONF_ALLOWED_AREAS: [],
                CONF_DEFAULT_ROOM: "Living Room",
                CONF_INCLUDE_ENTITIES: [],
                CONF_EXCLUDE_ENTITIES: [],
            }
        ]
    }
    entry.title = "HomeKit Bridge: Test Bridge"
    entry.version = 2
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    return entry


@pytest.fixture
def mock_entity_registry() -> MagicMock:
    """Create a mock entity registry."""
    registry = MagicMock()

    entity_with_area = MagicMock()
    entity_with_area.entity_id = "light.living_room"
    entity_with_area.area_id = "area_living_room"
    entity_with_area.device_id = None

    entity_with_device = MagicMock()
    entity_with_device.entity_id = "switch.bedroom"
    entity_with_device.area_id = None
    entity_with_device.device_id = "device_1"

    entity_without_area = MagicMock()
    entity_without_area.entity_id = "sensor.unknown"
    entity_without_area.area_id = None
    entity_without_area.device_id = None

    registry.entities = {
        entry.entity_id: entry
        for entry in (
            entity_with_area,
            entity_with_device,
            entity_without_area,
        )
    }

    def get_entity(entity_id: str):
        return registry.entities.get(entity_id)

    registry.async_get = get_entity
    return registry


@pytest.fixture
def mock_device_registry() -> MagicMock:
    """Create a mock device registry."""
    registry = MagicMock()

    device = MagicMock()
    device.area_id = "area_bedroom"

    def get_device(device_id: str):
        if device_id == "device_1":
            return device
        return None

    registry.async_get = get_device
    return registry


@pytest.fixture
def mock_area_registry() -> MagicMock:
    """Create a mock area registry."""
    registry = MagicMock()

    living_room = MagicMock()
    living_room.name = "Living Room"
    living_room.id = "area_living_room"

    bedroom = MagicMock()
    bedroom.name = "Bedroom"
    bedroom.id = "area_bedroom"

    def get_area(area_id: str):
        if area_id == "area_living_room":
            return living_room
        elif area_id == "area_bedroom":
            return bedroom
        return None

    registry.async_get_area = get_area

    # For config flow - list all areas
    registry.async_list_areas = MagicMock(return_value=[living_room, bedroom])

    return registry


