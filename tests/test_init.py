"""Tests for the HomeKit Room Sync integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.homekit_room_sync import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.homekit_room_sync.const import DOMAIN


class TestIntegrationSetup:
    """Tests for integration setup and unload."""

    @pytest.mark.asyncio
    async def test_async_setup_entry(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test successful setup of config entry."""
        with patch(
            "custom_components.homekit_room_sync.HomeKitRoomSyncCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator.async_sync_rooms = AsyncMock(return_value=True)
            mock_coordinator_class.return_value = mock_coordinator

            result = await async_setup_entry(mock_hass, mock_config_entry)

        assert result is True
        assert DOMAIN in mock_hass.data
        assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

        # Verify event listeners were registered
        assert mock_hass.bus.async_listen.call_count == 2

        # Verify initial sync was called
        mock_coordinator.async_sync_rooms.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_unload_entry(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test successful unload of config entry."""
        # Set up the data structure as if setup was called
        mock_unsub = MagicMock()
        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "coordinator": MagicMock(),
                "listeners": [mock_unsub, mock_unsub],
                "debounce_cancel": None,
            }
        }

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True
        assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]

        # Verify listeners were removed
        assert mock_unsub.call_count == 2

    @pytest.mark.asyncio
    async def test_async_unload_entry_with_pending_sync(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test unload cancels pending sync."""
        mock_cancel = MagicMock()
        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "coordinator": MagicMock(),
                "listeners": [],
                "debounce_cancel": mock_cancel,
            }
        }

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True
        mock_cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_unload_entry_not_loaded(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test unload when entry was never loaded."""
        mock_hass.data[DOMAIN] = {}

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True


class TestEventHandling:
    """Tests for event handling and debouncing."""

    @pytest.mark.asyncio
    async def test_schedule_sync_debouncing(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test that sync is debounced on multiple events."""
        with (
            patch(
                "custom_components.homekit_room_sync.HomeKitRoomSyncCoordinator"
            ) as mock_coordinator_class,
            patch(
                "custom_components.homekit_room_sync.async_call_later"
            ) as mock_call_later,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_sync_rooms = AsyncMock(return_value=True)
            mock_coordinator_class.return_value = mock_coordinator

            # Mock async_call_later to return a cancel function
            mock_cancel = MagicMock()
            mock_call_later.return_value = mock_cancel

            await async_setup_entry(mock_hass, mock_config_entry)

            # Get the schedule_sync callback
            calls = mock_hass.bus.async_listen.call_args_list
            assert len(calls) == 2

            # Extract the callback from the first listener
            schedule_sync = calls[0][0][1]

            # Simulate multiple events
            schedule_sync(None)
            schedule_sync(None)
            schedule_sync(None)

            # The debounce cancel should have been called
            # (at least once to cancel previous pending sync)
            assert mock_cancel.call_count >= 1

