"""Tests for the HomeKit Room Sync coordinator."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.homekit_room_sync.bridge_manager import ManagedBridgeConfig
from custom_components.homekit_room_sync.coordinator import (
    HomeKitRoomSyncCoordinator,
)
from custom_components.homekit_room_sync.storage import HomeKitStorageClient


@pytest.fixture
def bridge_config() -> ManagedBridgeConfig:
    """Return a base bridge configuration."""
    return ManagedBridgeConfig(
        bridge_id="test_bridge",
        friendly_name="Test Bridge",
        allowed_areas=set(),
        include_entities=set(),
        exclude_entities=set(),
        default_room="Living Room",
    )


def _create_coordinator(
    hass: MagicMock,
    entry: MagicMock,
    config: ManagedBridgeConfig,
) -> HomeKitRoomSyncCoordinator:
    storage = HomeKitStorageClient(hass)
    return HomeKitRoomSyncCoordinator(hass, entry, config, storage)


@pytest.mark.asyncio
async def test_sync_returns_false_when_storage_missing(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    bridge_config: ManagedBridgeConfig,
) -> None:
    """Ensure sync aborts if the HomeKit storage file does not exist."""
    mock_hass.config.path = MagicMock(return_value="/does/not/exist")
    coordinator = _create_coordinator(mock_hass, mock_config_entry, bridge_config)

    assert await coordinator.async_sync_rooms() is False


@pytest.mark.asyncio
async def test_sync_updates_room_assignments(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_entity_registry: MagicMock,
    mock_device_registry: MagicMock,
    mock_area_registry: MagicMock,
    temp_storage_dir: Path,
    sample_homekit_storage: dict[str, Any],
    bridge_config: ManagedBridgeConfig,
) -> None:
    """Verify that areas and default rooms are written back to storage."""
    storage_file = temp_storage_dir / "homekit.test_bridge.state"
    storage_file.write_text(json.dumps(sample_homekit_storage))
    mock_hass.config.path = MagicMock(return_value=str(temp_storage_dir.parent))

    coordinator = _create_coordinator(mock_hass, mock_config_entry, bridge_config)

    with (
        patch(
            "custom_components.homekit_room_sync.coordinator.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.coordinator.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.coordinator.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        result = await coordinator.async_sync_rooms()

    assert result is True
    updated = json.loads(storage_file.read_text())
    accessories = updated["data"]["accessories"]
    light = next(acc for acc in accessories if acc["entity_id"] == "light.living_room")
    assert light["room_name"] == "Living Room"
    switch = next(acc for acc in accessories if acc["entity_id"] == "switch.bedroom")
    assert switch["room_name"] == "Bedroom"
    sensor = next(acc for acc in accessories if acc["entity_id"] == "sensor.unknown")
    assert sensor["room_name"] == "Living Room"


@pytest.mark.asyncio
async def test_sync_respects_area_and_override_filters(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_entity_registry: MagicMock,
    mock_device_registry: MagicMock,
    mock_area_registry: MagicMock,
    temp_storage_dir: Path,
    sample_homekit_storage: dict[str, Any],
    bridge_config: ManagedBridgeConfig,
) -> None:
    """Entities outside allowed areas should be removed unless explicitly included."""
    storage_file = temp_storage_dir / "homekit.test_bridge.state"
    storage_file.write_text(json.dumps(sample_homekit_storage))
    mock_hass.config.path = MagicMock(return_value=str(temp_storage_dir.parent))

    filtered_config = replace(
        bridge_config,
        allowed_areas={"area_living_room"},
        include_entities={"sensor.unknown"},
        exclude_entities={"switch.bedroom"},
    )
    coordinator = _create_coordinator(mock_hass, mock_config_entry, filtered_config)

    with (
        patch(
            "custom_components.homekit_room_sync.coordinator.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.coordinator.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.coordinator.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        result = await coordinator.async_sync_rooms()

    assert result is True

    updated = json.loads(storage_file.read_text())
    entity_ids = [acc["entity_id"] for acc in updated["data"]["accessories"]]
    assert "light.living_room" in entity_ids
    assert "sensor.unknown" in entity_ids  # explicitly included
    assert "switch.bedroom" not in entity_ids  # explicitly excluded

