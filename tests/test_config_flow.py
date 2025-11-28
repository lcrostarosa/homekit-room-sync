"""Tests for the HomeKit Room Sync config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.homekit_room_sync.config_flow import (
    HomeKitRoomSyncConfigFlow,
)
from custom_components.homekit_room_sync.const import (
    CONF_BRIDGE_NAME,
    CONF_DEFAULT_ROOM,
    DOMAIN,
)


class TestHomeKitRoomSyncConfigFlow:
    """Tests for HomeKitRoomSyncConfigFlow."""

    @pytest.fixture
    def flow(self) -> HomeKitRoomSyncConfigFlow:
        """Create a config flow instance."""
        flow = HomeKitRoomSyncConfigFlow()
        flow.hass = MagicMock()
        flow.hass.config_entries = MagicMock()
        return flow

    @pytest.mark.asyncio
    async def test_step_user_no_bridges(self, flow: HomeKitRoomSyncConfigFlow) -> None:
        """Test user step when no bridges are found."""
        with patch(
            "custom_components.homekit_room_sync.config_flow."
            "HomeKitRoomSyncCoordinator.get_available_bridges",
            return_value=[],
        ):
            flow.hass.async_add_executor_job = MagicMock(return_value=[])
            result = await flow.async_step_user()

        assert result["type"] == "abort"
        assert result["reason"] == "no_bridges"

    @pytest.mark.asyncio
    async def test_step_user_shows_form(
        self, flow: HomeKitRoomSyncConfigFlow
    ) -> None:
        """Test user step shows form with available bridges."""
        flow._async_current_entries = MagicMock(return_value=[])

        async def mock_executor(func, *args):
            return func(*args)

        flow.hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.homekit_room_sync.config_flow."
            "HomeKitRoomSyncCoordinator.get_available_bridges",
            return_value=["bridge1", "bridge2"],
        ):
            result = await flow.async_step_user()

        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_step_user_all_bridges_configured(
        self, flow: HomeKitRoomSyncConfigFlow
    ) -> None:
        """Test user step when all bridges are already configured."""
        # Mock existing entry
        existing_entry = MagicMock()
        existing_entry.data = {CONF_BRIDGE_NAME: "bridge1"}
        flow._async_current_entries = MagicMock(return_value=[existing_entry])

        async def mock_executor(func, *args):
            return func(*args)

        flow.hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.homekit_room_sync.config_flow."
            "HomeKitRoomSyncCoordinator.get_available_bridges",
            return_value=["bridge1"],
        ):
            result = await flow.async_step_user()

        assert result["type"] == "abort"
        assert result["reason"] == "all_bridges_configured"

    @pytest.mark.asyncio
    async def test_step_user_selects_bridge(
        self, flow: HomeKitRoomSyncConfigFlow
    ) -> None:
        """Test user step when selecting a bridge."""
        flow._async_current_entries = MagicMock(return_value=[])

        async def mock_executor(func, *args):
            return func(*args)

        flow.hass.async_add_executor_job = mock_executor

        with patch(
            "custom_components.homekit_room_sync.config_flow."
            "HomeKitRoomSyncCoordinator.get_available_bridges",
            return_value=["bridge1", "bridge2"],
        ):
            result = await flow.async_step_user({CONF_BRIDGE_NAME: "bridge1"})

        # Should proceed to room step
        assert result["type"] == "form"
        assert result["step_id"] == "room"
        assert flow._bridge_name == "bridge1"

    @pytest.mark.asyncio
    async def test_step_room_creates_entry(
        self, flow: HomeKitRoomSyncConfigFlow, mock_area_registry: MagicMock
    ) -> None:
        """Test room step creates config entry."""
        flow._bridge_name = "bridge1"

        with patch(
            "custom_components.homekit_room_sync.config_flow.ar.async_get",
            return_value=mock_area_registry,
        ):
            result = await flow.async_step_room({CONF_DEFAULT_ROOM: "Living Room"})

        assert result["type"] == "create_entry"
        assert result["title"] == "HomeKit Bridge: bridge1"
        assert result["data"] == {
            CONF_BRIDGE_NAME: "bridge1",
            CONF_DEFAULT_ROOM: "Living Room",
        }

    @pytest.mark.asyncio
    async def test_step_room_no_default_room(
        self, flow: HomeKitRoomSyncConfigFlow, mock_area_registry: MagicMock
    ) -> None:
        """Test room step with no default room selected."""
        flow._bridge_name = "bridge1"

        with patch(
            "custom_components.homekit_room_sync.config_flow.ar.async_get",
            return_value=mock_area_registry,
        ):
            result = await flow.async_step_room({CONF_DEFAULT_ROOM: ""})

        assert result["type"] == "create_entry"
        assert result["data"][CONF_DEFAULT_ROOM] is None


class TestHomeKitRoomSyncOptionsFlow:
    """Tests for HomeKitRoomSyncOptionsFlow."""

    @pytest.mark.asyncio
    async def test_options_flow_init(
        self, mock_config_entry: MagicMock, mock_area_registry: MagicMock
    ) -> None:
        """Test options flow initialization."""
        from custom_components.homekit_room_sync.config_flow import (
            HomeKitRoomSyncOptionsFlow,
        )

        flow = HomeKitRoomSyncOptionsFlow(mock_config_entry)
        flow.hass = MagicMock()
        flow.hass.config_entries = MagicMock()

        with patch(
            "custom_components.homekit_room_sync.config_flow.ar.async_get",
            return_value=mock_area_registry,
        ):
            result = await flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_flow_update(
        self, mock_config_entry: MagicMock, mock_area_registry: MagicMock
    ) -> None:
        """Test options flow updating default room."""
        from custom_components.homekit_room_sync.config_flow import (
            HomeKitRoomSyncOptionsFlow,
        )

        flow = HomeKitRoomSyncOptionsFlow(mock_config_entry)
        flow.hass = MagicMock()
        flow.hass.config_entries = MagicMock()
        flow.hass.config_entries.async_update_entry = MagicMock()

        with patch(
            "custom_components.homekit_room_sync.config_flow.ar.async_get",
            return_value=mock_area_registry,
        ):
            result = await flow.async_step_init({CONF_DEFAULT_ROOM: "Bedroom"})

        assert result["type"] == "create_entry"
        flow.hass.config_entries.async_update_entry.assert_called_once()

