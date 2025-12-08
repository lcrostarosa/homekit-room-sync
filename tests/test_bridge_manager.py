"""Tests for the HomeKitBridgeManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.homekit_room_sync.bridge_manager import (
    _as_str_set,
    _pick_new_port,
    BridgeConfig,
    HomeKitBridgeManager,
    parse_bridge_configs,
)
from custom_components.homekit_room_sync.const import CONF_BRIDGES, HOMEKIT_DOMAIN


@pytest.mark.asyncio
async def test_manager_updates_homekit_entry(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_entity_registry: MagicMock,
    mock_device_registry: MagicMock,
    mock_area_registry: MagicMock,
    mock_homekit_entry: MagicMock,
) -> None:
    """Manager should update filter + entity_config based on areas."""
    config = BridgeConfig(
        entry_id=mock_homekit_entry.entry_id,
        areas=frozenset({"area_living_room", "area_bedroom"}),
        include_entities=frozenset(),
        exclude_entities=frozenset(),
    )
    manager = HomeKitBridgeManager(mock_hass, mock_config_entry, [config])

    with (
        patch(
            "custom_components.homekit_room_sync.bridge_manager.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.bridge_manager.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.bridge_manager.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        result = await manager.async_sync()

    assert result is True
    mock_hass.config_entries.async_update_entry.assert_called_once()
    update_kwargs = mock_hass.config_entries.async_update_entry.call_args[1]
    updated_data = update_kwargs["data"]
    assert updated_data["filter"]["include_entities"] == [
        "light.living_room",
        "switch.bedroom",
    ]
    entity_config = updated_data["entity_config"]
    assert entity_config["light.living_room"]["room"] == "Living Room"
    assert entity_config["switch.bedroom"]["room"] == "Bedroom"
    mock_hass.config_entries.async_reload.assert_awaited_once()


@pytest.mark.asyncio
async def test_manager_respects_manual_overrides(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_entity_registry: MagicMock,
    mock_device_registry: MagicMock,
    mock_area_registry: MagicMock,
    mock_homekit_entry: MagicMock,
) -> None:
    """Include/exclude overrides should adjust final entity list."""
    config = BridgeConfig(
        entry_id=mock_homekit_entry.entry_id,
        areas=frozenset({"area_living_room"}),
        include_entities=frozenset({"sensor.unknown"}),
        exclude_entities=frozenset({"switch.bedroom"}),
    )
    manager = HomeKitBridgeManager(mock_hass, mock_config_entry, [config])

    with (
        patch(
            "custom_components.homekit_room_sync.bridge_manager.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.bridge_manager.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.bridge_manager.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        result = await manager.async_sync()

    assert result is True
    update_kwargs = mock_hass.config_entries.async_update_entry.call_args[1]
    updated_entities = update_kwargs["data"]["filter"]["include_entities"]
    assert updated_entities == ["light.living_room", "sensor.unknown"]
    entity_config = update_kwargs["data"]["entity_config"]
    assert entity_config["sensor.unknown"]["room"] is None


def test_as_str_set_converts_non_strings() -> None:
    """_as_str_set should include non-string iterables as strings."""
    data = {1, "two", 3}
    assert _as_str_set(data) == {"1", "two", "3"}

    # Strings/bytes are treated as scalar, not iterable for our purposes
    assert _as_str_set("abc") == set()
    assert _as_str_set(b"bytes") == set()


def test_parse_bridge_configs_ignores_string_conf() -> None:
    """parse_bridge_configs should not iterate over string/bytes configs."""
    entry = MagicMock()
    entry.data = {CONF_BRIDGES: "not-a-list"}
    assert parse_bridge_configs(entry) == []


@pytest.mark.asyncio
async def test_manager_resolves_duplicate_port(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_entity_registry: MagicMock,
    mock_device_registry: MagicMock,
    mock_area_registry: MagicMock,
    mock_homekit_entry: MagicMock,
) -> None:
    """A duplicate port should be reassigned before reloading HomeKit."""
    mock_homekit_entry.data = {
        "filter": {},
        "entity_config": {},
        "port": 21064,
    }

    other_entry = MagicMock()
    other_entry.entry_id = "other_entry"
    other_entry.data = {"port": 21064}

    def _async_entries(domain: str | None = None):
        if domain == HOMEKIT_DOMAIN:
            return [mock_homekit_entry, other_entry]
        return []

    mock_hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)

    config = BridgeConfig(
        entry_id=mock_homekit_entry.entry_id,
        areas=frozenset({"area_living_room"}),
        include_entities=frozenset(),
        exclude_entities=frozenset(),
    )
    manager = HomeKitBridgeManager(mock_hass, mock_config_entry, [config])

    with (
        patch(
            "custom_components.homekit_room_sync.bridge_manager.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.bridge_manager.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.bridge_manager.area_registry.async_get",
            return_value=mock_area_registry,
        ),
    ):
        result = await manager.async_sync()

    assert result is True
    expected_port = _pick_new_port(mock_homekit_entry.entry_id, {21064})
    update_kwargs = mock_hass.config_entries.async_update_entry.call_args[1]
    assert update_kwargs["data"]["port"] == expected_port
    mock_hass.config_entries.async_reload.assert_awaited_once()


@pytest.mark.asyncio
async def test_port_conflict_triggers_update_without_filter_change(
    mock_hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_entity_registry: MagicMock,
    mock_device_registry: MagicMock,
    mock_area_registry: MagicMock,
    mock_homekit_entry: MagicMock,
) -> None:
    """Port conflicts are resolved even when no filter changes are detected."""
    mock_homekit_entry.data = {
        "filter": {},
        "entity_config": {},
        "port": 21064,
    }

    other_entry = MagicMock()
    other_entry.entry_id = "other_entry"
    other_entry.data = {"port": 21064}

    def _async_entries(domain: str | None = None):
        if domain == HOMEKIT_DOMAIN:
            return [mock_homekit_entry, other_entry]
        return []

    mock_hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)

    config = BridgeConfig(
        entry_id=mock_homekit_entry.entry_id,
        areas=frozenset({"area_living_room"}),
        include_entities=frozenset(),
        exclude_entities=frozenset(),
    )
    manager = HomeKitBridgeManager(mock_hass, mock_config_entry, [config])

    with (
        patch(
            "custom_components.homekit_room_sync.bridge_manager.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.bridge_manager.device_registry.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.homekit_room_sync.bridge_manager.area_registry.async_get",
            return_value=mock_area_registry,
        ),
        patch.object(
            HomeKitBridgeManager,
            "_build_updated_data",
            return_value=None,
        ),
    ):
        result = await manager.async_sync()

    assert result is True
    expected_port = _pick_new_port(mock_homekit_entry.entry_id, {21064})
    update_kwargs = mock_hass.config_entries.async_update_entry.call_args[1]
    assert update_kwargs["data"]["port"] == expected_port
    mock_hass.config_entries.async_reload.assert_awaited_once()
