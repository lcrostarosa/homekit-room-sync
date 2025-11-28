"""Mock homeassistant.helpers.area_registry module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from ..core import HomeAssistant


class AreaEntry:
    """Mock AreaEntry class."""

    def __init__(self, area_id: str, name: str) -> None:
        """Initialize mock area entry."""
        self.id = area_id
        self.name = name


class AreaRegistry:
    """Mock AreaRegistry class."""

    def __init__(self) -> None:
        """Initialize mock area registry."""
        self._areas: dict[str, AreaEntry] = {}

    def async_get_area(self, area_id: str) -> AreaEntry | None:
        """Get an area by ID."""
        return self._areas.get(area_id)

    def async_list_areas(self) -> list[AreaEntry]:
        """List all areas."""
        return list(self._areas.values())


def async_get(hass: HomeAssistant) -> AreaRegistry:
    """Get the area registry."""
    return MagicMock(spec=AreaRegistry)

