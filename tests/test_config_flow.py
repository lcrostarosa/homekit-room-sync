"""Tests for the HomeKit Room Sync config and options flows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.homekit_room_sync.config_flow import (
    HomeKitRoomSyncConfigFlow,
    HomeKitRoomSyncOptionsFlow,
)
from custom_components.homekit_room_sync.const import (
    CONF_ALLOWED_AREAS,
    CONF_BRIDGE_ID,
    CONF_BRIDGE_TITLE,
    CONF_DEFAULT_ROOM,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITIES,
    CONF_MANAGED_BRIDGES,
)


@pytest.fixture(autouse=True)
def mock_exposure_plan(monkeypatch):
    plan = SimpleNamespace(include_entities=[], rooms_by_entity={}, allowed_entities=set())

    def _fake_plan(hass, config):
        return plan

    monkeypatch.setattr(
        "custom_components.homekit_room_sync.config_flow.build_exposure_plan",
        _fake_plan,
    )
    return plan


@pytest.fixture
def flow() -> HomeKitRoomSyncConfigFlow:
    """Create a config flow instance."""
    flow = HomeKitRoomSyncConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_entries = MagicMock(return_value=[])
    return flow


@pytest.mark.asyncio
async def test_step_user_no_bridges(flow: HomeKitRoomSyncConfigFlow) -> None:
    """Abort when no HomeKit bridges are discovered."""
    with patch(
        "custom_components.homekit_room_sync.config_flow.async_discover_bridges",
        AsyncMock(return_value={}),
    ):
        result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "no_bridges"


@pytest.mark.asyncio
async def test_step_user_all_bridges_configured(flow: HomeKitRoomSyncConfigFlow) -> None:
    """Abort when all bridges are already configured."""
    existing_entry = MagicMock()
    existing_entry.data = {
        CONF_MANAGED_BRIDGES: [{CONF_BRIDGE_ID: "bridge1"}],
    }
    flow._async_current_entries = MagicMock(return_value=[existing_entry])

    with patch(
        "custom_components.homekit_room_sync.config_flow.async_discover_bridges",
        AsyncMock(return_value={"bridge1": "Bridge 1"}),
    ):
        result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "all_bridges_configured"


@pytest.mark.asyncio
async def test_step_user_to_bridge(flow: HomeKitRoomSyncConfigFlow) -> None:
    """Selecting bridges should advance to bridge configuration."""
    flow._async_current_entries = MagicMock(return_value=[])

    with patch(
        "custom_components.homekit_room_sync.config_flow.async_discover_bridges",
        AsyncMock(return_value={"bridge1": "Bridge 1", "bridge2": "Bridge 2"}),
    ):
        result = await flow.async_step_user(
            {CONF_MANAGED_BRIDGES: ["bridge1", "bridge2"]}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "bridge"


@pytest.mark.asyncio
async def test_bridge_step_creates_entry(
    flow: HomeKitRoomSyncConfigFlow,
    mock_area_registry: MagicMock,
) -> None:
    """Bridge step should collect filters and create entry."""
    flow._async_current_entries = MagicMock(return_value=[])

    with patch(
        "custom_components.homekit_room_sync.config_flow.async_discover_bridges",
        AsyncMock(return_value={"bridge1": "Bridge 1"}),
    ):
        await flow.async_step_user({CONF_MANAGED_BRIDGES: ["bridge1"]})

    with patch(
        "custom_components.homekit_room_sync.config_flow.area_registry.async_get",
        return_value=mock_area_registry,
    ):
        result = await flow.async_step_bridge(
            {
                CONF_ALLOWED_AREAS: ["area_living_room"],
                CONF_DEFAULT_ROOM: "area_bedroom",
                CONF_INCLUDE_ENTITIES: "light.kitchen\nswitch.desk",
                CONF_EXCLUDE_ENTITIES: "switch.desk,sensor.outdoor",
            }
        )

    assert result["type"] == "create_entry"
    data = result["data"][CONF_MANAGED_BRIDGES][0]
    assert data[CONF_BRIDGE_ID] == "bridge1"
    assert data[CONF_BRIDGE_TITLE] == "Bridge 1"
    assert data[CONF_ALLOWED_AREAS] == ["area_living_room"]
    assert data[CONF_DEFAULT_ROOM] == "Bedroom"
    assert data[CONF_INCLUDE_ENTITIES] == ["light.kitchen", "switch.desk"]
    # Exclude should remove duplicates present in include
    assert data[CONF_EXCLUDE_ENTITIES] == ["sensor.outdoor"]


@pytest.mark.asyncio
async def test_options_flow_updates_entry(
    mock_config_entry: MagicMock,
    mock_area_registry: MagicMock,
) -> None:
    """Options flow should persist updated bridge filters."""
    flow = HomeKitRoomSyncOptionsFlow(mock_config_entry)
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_entries = MagicMock(return_value=[mock_config_entry])
    flow.hass.config_entries.async_update_entry = MagicMock()

    with patch(
        "custom_components.homekit_room_sync.config_flow.async_discover_bridges",
        AsyncMock(return_value={"test_bridge": "Test Bridge"}),
    ):
        await flow.async_step_init({CONF_MANAGED_BRIDGES: ["test_bridge"]})

    with patch(
        "custom_components.homekit_room_sync.config_flow.area_registry.async_get",
        return_value=mock_area_registry,
    ):
        result = await flow.async_step_bridge(
            {
                CONF_ALLOWED_AREAS: ["area_bedroom"],
                CONF_DEFAULT_ROOM: "",
                CONF_INCLUDE_ENTITIES: "",
                CONF_EXCLUDE_ENTITIES: "",
            }
        )

    assert result["type"] == "create_entry"
    flow.hass.config_entries.async_update_entry.assert_called_once()
    updated_data = flow.hass.config_entries.async_update_entry.call_args[1]["data"]
    bridge_data = updated_data[CONF_MANAGED_BRIDGES][0]
    assert bridge_data[CONF_ALLOWED_AREAS] == ["area_bedroom"]
    assert bridge_data[CONF_DEFAULT_ROOM] is None or bridge_data[CONF_DEFAULT_ROOM] == ""

