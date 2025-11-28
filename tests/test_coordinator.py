"""Tests for the HomeKit Room Sync coordinator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.homekit_room_sync.coordinator import (
    HomeKitRoomSyncCoordinator,
)


class TestHomeKitRoomSyncCoordinator:
    """Tests for HomeKitRoomSyncCoordinator."""

    def test_init(self, mock_hass: MagicMock, mock_config_entry: MagicMock) -> None:
        """Test coordinator initialization."""
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        assert coordinator.hass == mock_hass
        assert coordinator.entry == mock_config_entry
        assert coordinator._bridge_name == "test_bridge"
        assert coordinator._default_room == "Living Room"

    def test_bridge_storage_file_path(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """Test bridge storage file path generation."""
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        expected_path = Path("/config/.storage/homekit.test_bridge.state")
        assert coordinator.bridge_storage_file == expected_path

    @pytest.mark.asyncio
    async def test_async_sync_rooms_file_not_found(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """Test sync when storage file doesn't exist."""
        mock_hass.config.path = MagicMock(return_value="/nonexistent")
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        result = await coordinator.async_sync_rooms()

        assert result is False

    @pytest.mark.asyncio
    async def test_async_sync_rooms_success(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
        mock_entity_registry: MagicMock,
        mock_device_registry: MagicMock,
        mock_area_registry: MagicMock,
        temp_storage_dir: Path,
        sample_homekit_storage: dict[str, Any],
    ) -> None:
        """Test successful room sync."""
        # Set up storage file
        storage_file = temp_storage_dir / "homekit.test_bridge.state"
        storage_file.write_text(json.dumps(sample_homekit_storage))

        # Configure mock hass to use temp directory
        mock_hass.config.path = MagicMock(
            return_value=str(temp_storage_dir.parent)
        )

        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        with (
            patch(
                "custom_components.homekit_room_sync.coordinator.er.async_get",
                return_value=mock_entity_registry,
            ),
            patch(
                "custom_components.homekit_room_sync.coordinator.dr.async_get",
                return_value=mock_device_registry,
            ),
            patch(
                "custom_components.homekit_room_sync.coordinator.ar.async_get",
                return_value=mock_area_registry,
            ),
        ):
            result = await coordinator.async_sync_rooms()

        assert result is True

        # Verify the storage file was updated
        updated_data = json.loads(storage_file.read_text())
        accessories = updated_data["data"]["accessories"]

        # light.living_room should be in "Living Room" (from entity area)
        light = next(a for a in accessories if a["entity_id"] == "light.living_room")
        assert light["room_name"] == "Living Room"

        # switch.bedroom should be in "Bedroom" (from device area)
        switch = next(a for a in accessories if a["entity_id"] == "switch.bedroom")
        assert switch["room_name"] == "Bedroom"

        # sensor.unknown should use default room
        sensor = next(a for a in accessories if a["entity_id"] == "sensor.unknown")
        assert sensor["room_name"] == "Living Room"

    @pytest.mark.asyncio
    async def test_async_sync_rooms_no_changes(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
        mock_entity_registry: MagicMock,
        mock_device_registry: MagicMock,
        mock_area_registry: MagicMock,
        temp_storage_dir: Path,
    ) -> None:
        """Test sync when no changes are needed."""
        # Create storage with already correct rooms
        storage_data = {
            "version": 1,
            "key": "homekit.test_bridge.state",
            "data": {
                "accessories": [
                    {
                        "entity_id": "light.living_room",
                        "room_name": "Living Room",
                    },
                ]
            },
        }
        storage_file = temp_storage_dir / "homekit.test_bridge.state"
        storage_file.write_text(json.dumps(storage_data))

        mock_hass.config.path = MagicMock(
            return_value=str(temp_storage_dir.parent)
        )

        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        with (
            patch(
                "custom_components.homekit_room_sync.coordinator.er.async_get",
                return_value=mock_entity_registry,
            ),
            patch(
                "custom_components.homekit_room_sync.coordinator.dr.async_get",
                return_value=mock_device_registry,
            ),
            patch(
                "custom_components.homekit_room_sync.coordinator.ar.async_get",
                return_value=mock_area_registry,
            ),
        ):
            result = await coordinator.async_sync_rooms()

        assert result is True
        # HomeKit reload should NOT be called since no changes
        mock_hass.services.async_call.assert_not_called()

    def test_get_room_for_entity_with_area(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
        mock_entity_registry: MagicMock,
        mock_device_registry: MagicMock,
        mock_area_registry: MagicMock,
    ) -> None:
        """Test getting room for entity with direct area assignment."""
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        room = coordinator._get_room_for_entity(
            "light.living_room",
            mock_entity_registry,
            mock_device_registry,
            mock_area_registry,
        )

        assert room == "Living Room"

    def test_get_room_for_entity_with_device_area(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
        mock_entity_registry: MagicMock,
        mock_device_registry: MagicMock,
        mock_area_registry: MagicMock,
    ) -> None:
        """Test getting room for entity via device area."""
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        room = coordinator._get_room_for_entity(
            "switch.bedroom",
            mock_entity_registry,
            mock_device_registry,
            mock_area_registry,
        )

        assert room == "Bedroom"

    def test_get_room_for_entity_fallback_default(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
        mock_entity_registry: MagicMock,
        mock_device_registry: MagicMock,
        mock_area_registry: MagicMock,
    ) -> None:
        """Test getting room for entity without area falls back to default."""
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        room = coordinator._get_room_for_entity(
            "sensor.unknown",
            mock_entity_registry,
            mock_device_registry,
            mock_area_registry,
        )

        assert room == "Living Room"  # Default room from config

    def test_get_room_for_unknown_entity(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
        mock_entity_registry: MagicMock,
        mock_device_registry: MagicMock,
        mock_area_registry: MagicMock,
    ) -> None:
        """Test getting room for entity not in registry."""
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        room = coordinator._get_room_for_entity(
            "light.nonexistent",
            mock_entity_registry,
            mock_device_registry,
            mock_area_registry,
        )

        assert room == "Living Room"  # Falls back to default

    def test_get_available_bridges(
        self, mock_hass: MagicMock, temp_storage_dir: Path
    ) -> None:
        """Test discovering available HomeKit bridges."""
        # Create mock bridge files
        (temp_storage_dir / "homekit.bridge1.state").write_text("{}")
        (temp_storage_dir / "homekit.bridge2.state").write_text("{}")
        (temp_storage_dir / "other_file.json").write_text("{}")

        mock_hass.config.path = MagicMock(
            return_value=str(temp_storage_dir.parent)
        )

        bridges = HomeKitRoomSyncCoordinator.get_available_bridges(mock_hass)

        assert bridges == ["bridge1", "bridge2"]

    def test_get_available_bridges_no_storage(
        self, mock_hass: MagicMock, tmp_path: Path
    ) -> None:
        """Test discovering bridges when storage dir doesn't exist."""
        mock_hass.config.path = MagicMock(return_value=str(tmp_path / "nonexistent"))

        bridges = HomeKitRoomSyncCoordinator.get_available_bridges(mock_hass)

        assert bridges == []


class TestCoordinatorStorageOperations:
    """Tests for coordinator storage operations."""

    @pytest.mark.asyncio
    async def test_read_storage_file_invalid_json(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock, tmp_path: Path
    ) -> None:
        """Test reading invalid JSON storage file."""
        storage_dir = tmp_path / ".storage"
        storage_dir.mkdir()
        storage_file = storage_dir / "homekit.test_bridge.state"
        storage_file.write_text("invalid json {{{")

        mock_hass.config.path = MagicMock(return_value=str(tmp_path))
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        result = await coordinator._read_storage_file(storage_file)

        assert result is None

    @pytest.mark.asyncio
    async def test_read_storage_file_missing_data_key(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock, tmp_path: Path
    ) -> None:
        """Test reading storage file without 'data' key."""
        storage_dir = tmp_path / ".storage"
        storage_dir.mkdir()
        storage_file = storage_dir / "homekit.test_bridge.state"
        storage_file.write_text('{"version": 1}')

        mock_hass.config.path = MagicMock(return_value=str(tmp_path))
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        result = await coordinator._read_storage_file(storage_file)

        assert result is None

    @pytest.mark.asyncio
    async def test_create_backup(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock, tmp_path: Path
    ) -> None:
        """Test backup creation."""
        storage_dir = tmp_path / ".storage"
        storage_dir.mkdir()
        storage_file = storage_dir / "homekit.test_bridge.state"
        storage_file.write_text('{"test": "data"}')

        mock_hass.config.path = MagicMock(return_value=str(tmp_path))
        coordinator = HomeKitRoomSyncCoordinator(mock_hass, mock_config_entry)

        result = await coordinator._create_backup(storage_file)

        assert result is True
        backup_file = storage_file.with_suffix(".state.backup")
        assert backup_file.exists()
        assert backup_file.read_text() == '{"test": "data"}'

