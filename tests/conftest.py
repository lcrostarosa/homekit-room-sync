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
    config_validation,
    device_registry,
    entity_registry,
    event,
)

sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.config_entries"] = config_entries
sys.modules["homeassistant.helpers"] = homeassistant.helpers
sys.modules["homeassistant.helpers.area_registry"] = area_registry
sys.modules["homeassistant.helpers.config_validation"] = config_validation
sys.modules["homeassistant.helpers.device_registry"] = device_registry
sys.modules["homeassistant.helpers.entity_registry"] = entity_registry
sys.modules["homeassistant.helpers.event"] = event

from custom_components.homekit_room_sync.const import (
    CONF_AREAS,
    CONF_BRIDGES,
    CONF_ENTRY_ID,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITIES,
    DOMAIN,
    HOMEKIT_DOMAIN,
)


@pytest.fixture
def mock_homekit_entry() -> MagicMock:
    """Create a mock HomeKit config entry."""
    entry = MagicMock()
    entry.entry_id = "homekit_entry_1"
    entry.title = "Living Bridge"
    entry.data = {"filter": {}, "entity_config": {}}
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

    def _async_entries(domain: str | None = None):
        if domain == HOMEKIT_DOMAIN:
            return [mock_homekit_entry]
        if domain == DOMAIN:
            return []
        return []

    hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)
    hass.config_entries.async_get_entry = MagicMock(
        side_effect=lambda entry_id: mock_homekit_entry
        if entry_id == mock_homekit_entry.entry_id
        else None
    )
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    # Mock async_add_executor_job to run synchronously
    async def mock_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs)

    hass.async_add_executor_job = mock_executor_job
    return hass


@pytest.fixture
def mock_config_entry(mock_homekit_entry: MagicMock) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_BRIDGES: [
            {
                CONF_ENTRY_ID: mock_homekit_entry.entry_id,
                CONF_AREAS: [],
                CONF_INCLUDE_ENTITIES: [],
                CONF_EXCLUDE_ENTITIES: [],
            }
        ]
    }
    entry.title = "HomeKit Bridge: Living Bridge"
    entry.version = 3
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    return entry


@pytest.fixture
def mock_entity_registry() -> MagicMock:
    """Create a mock entity registry."""
    registry = MagicMock()

    # Create mock entity entries
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

    entity_map = {
        "light.living_room": entity_with_area,
        "switch.bedroom": entity_with_device,
        "sensor.unknown": entity_without_area,
    }

    def get_entity(entity_id: str):
        return entity_map.get(entity_id)

    registry.async_get = get_entity
    registry.entities = entity_map
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


