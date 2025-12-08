"""Tests for the HomeKit Room Sync coordinator."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.homekit_room_sync.bridge_manager import ManagedBridgeConfig
from custom_components.homekit_room_sync.coordinator import HomeKitRoomSyncCoordinator


def _build_config(**overrides) -> ManagedBridgeConfig:
    base = {
        "bridge_id": "test_bridge",
        "friendly_name": "Test Bridge",
        "allowed_areas": set(),
        "include_entities": set(),
        "exclude_entities": set(),
        "default_room": "Living Room",
    }
    base.update(overrides)
    return ManagedBridgeConfig(**base)


@pytest.mark.asyncio
async def test_updates_filters_and_rooms(
    mock_hass,
    mock_config_entry,
    mock_entity_registry,
    mock_device_registry,
    mock_area_registry,
    mock_homekit_entry,
) -> None:
    """Coordinator should update include_entities and entity_config."""
    config = _build_config(allowed_areas={"area_living_room"})
    coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry, config)

    mock_homekit_entry.data = {"filter": {}, "entity_config": {}}
    mock_hass.config_entries.async_reload.reset_mock()

    with (
        patch(
            "custom_components.homekit_room_sync.exposure.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        result = await coordinator.async_sync_rooms()

    assert result is True
    data = mock_homekit_entry.data
    assert data["filter"]["include_entities"] == ["light.living_room"]
    assert data["filter"]["exclude_entities"] == []
    assert data["filter"]["include_areas"] == ["area_living_room"]
    assert data["entity_config"] == {
        "light.living_room": {"room": "Living Room"},
    }
    mock_hass.config_entries.async_reload.assert_awaited_once()


@pytest.mark.asyncio
async def test_include_and_exclude_overrides(
    mock_hass,
    mock_config_entry,
    mock_entity_registry,
    mock_device_registry,
    mock_area_registry,
    mock_homekit_entry,
) -> None:
    """Manual include/exclude lists should override area filters."""
    config = _build_config(
        allowed_areas={"area_living_room"},
        include_entities={"switch.bedroom"},
        exclude_entities={"light.living_room"},
    )
    coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry, config)

    mock_homekit_entry.data = {"filter": {}, "entity_config": {}}

    with (
        patch(
            "custom_components.homekit_room_sync.exposure.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        await coordinator.async_sync_rooms()

    data = mock_homekit_entry.data
    assert data["filter"]["include_entities"] == ["switch.bedroom"]
    assert data["filter"]["exclude_entities"] == ["light.living_room"]
    assert data["entity_config"]["switch.bedroom"]["room"] == "Bedroom"


@pytest.mark.asyncio
async def test_no_changes_skips_reload(
    mock_hass,
    mock_config_entry,
    mock_entity_registry,
    mock_device_registry,
    mock_area_registry,
    mock_homekit_entry,
) -> None:
    """Running twice without registry changes should avoid reload."""
    config = _build_config(allowed_areas={"area_living_room"})
    coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry, config)

    mock_homekit_entry.data = {"filter": {}, "entity_config": {}}

    with (
        patch(
            "custom_components.homekit_room_sync.exposure.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        await coordinator.async_sync_rooms()

    mock_hass.config_entries.async_reload.reset_mock()
    mock_hass.config_entries.async_update_entry.reset_mock()

    with (
        patch(
            "custom_components.homekit_room_sync.exposure.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        await coordinator.async_sync_rooms()

    mock_hass.config_entries.async_update_entry.assert_not_called()
    mock_hass.config_entries.async_reload.assert_not_called()


@pytest.mark.asyncio
async def test_area_move_triggers_update(
    mock_hass,
    mock_config_entry,
    mock_entity_registry,
    mock_device_registry,
    mock_area_registry,
    mock_homekit_entry,
) -> None:
    """Moving an entity into an allowed area should add it to the filter."""
    config = _build_config(allowed_areas={"area_living_room"})
    coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry, config)

    mock_homekit_entry.data = {"filter": {}, "entity_config": {}}

    with (
        patch(
            "custom_components.homekit_room_sync.exposure.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        await coordinator.async_sync_rooms()

    # Move the switch into the living room area
    mock_entity_registry.entities["switch.bedroom"].area_id = "area_living_room"
    mock_hass.config_entries.async_update_entry.reset_mock()

    with (
        patch(
            "custom_components.homekit_room_sync.exposure.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.exposure.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        await coordinator.async_sync_rooms()

    data = mock_homekit_entry.data
    assert set(data["filter"]["include_entities"]) == {
        "light.living_room",
        "switch.bedroom",
    }