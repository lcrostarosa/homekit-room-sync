"""Pytest fixtures for HomeKit Room Sync tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
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


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path = MagicMock(return_value="/config")
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock(return_value=MagicMock())
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    # Mock async_add_executor_job to run synchronously
    async def mock_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = mock_executor_job
    return hass


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "bridge_name": "test_bridge",
        "default_room": "Living Room",
    }
    entry.title = "HomeKit Bridge: test_bridge"
    entry.version = 1
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    return entry


@pytest.fixture
def mock_entity_registry() -> MagicMock:
    """Create a mock entity registry."""
    registry = MagicMock()

    # Create mock entity entries
    entity_with_area = MagicMock()
    entity_with_area.area_id = "area_living_room"
    entity_with_area.device_id = None

    entity_with_device = MagicMock()
    entity_with_device.area_id = None
    entity_with_device.device_id = "device_1"

    entity_without_area = MagicMock()
    entity_without_area.area_id = None
    entity_without_area.device_id = None

    def get_entity(entity_id: str):
        if entity_id == "light.living_room":
            return entity_with_area
        elif entity_id == "switch.bedroom":
            return entity_with_device
        elif entity_id == "sensor.unknown":
            return entity_without_area
        return None

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

    bedroom = MagicMock()
    bedroom.name = "Bedroom"

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


@pytest.fixture
def sample_homekit_storage() -> dict[str, Any]:
    """Create sample HomeKit storage data."""
    return {
        "version": 1,
        "key": "homekit.test_bridge.state",
        "data": {
            "accessories": [
                {
                    "entity_id": "light.living_room",
                    "room_name": "Default Room",
                },
                {
                    "entity_id": "switch.bedroom",
                    "room_name": "Default Room",
                },
                {
                    "entity_id": "sensor.unknown",
                    "room_name": None,
                },
            ]
        },
    }


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory."""
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def mock_storage_file(
    temp_storage_dir: Path, sample_homekit_storage: dict[str, Any]
) -> Path:
    """Create a mock HomeKit storage file."""
    storage_file = temp_storage_dir / "homekit.test_bridge.state"
    storage_file.write_text(json.dumps(sample_homekit_storage, indent=2))
    return storage_file
