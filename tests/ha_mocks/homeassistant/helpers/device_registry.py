"""Mock homeassistant.helpers.device_registry module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from ..core import HomeAssistant


class DeviceEntry:
    """Mock DeviceEntry class."""

    def __init__(self, device_id: str, area_id: str | None = None) -> None:
        """Initialize mock device entry."""
        self.id = device_id
        self.area_id = area_id


class DeviceRegistry:
    """Mock DeviceRegistry class."""

    def __init__(self) -> None:
        """Initialize mock device registry."""
        self._devices: dict[str, DeviceEntry] = {}

    def async_get(self, device_id: str) -> DeviceEntry | None:
        """Get a device by ID."""
        return self._devices.get(device_id)


def async_get(hass: HomeAssistant) -> DeviceRegistry:
    """Get the device registry."""
    return MagicMock(spec=DeviceRegistry)

