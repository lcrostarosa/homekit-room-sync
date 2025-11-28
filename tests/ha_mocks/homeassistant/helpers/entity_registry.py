"""Mock homeassistant.helpers.entity_registry module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from ..core import HomeAssistant


class EntityEntry:
    """Mock EntityEntry class."""

    def __init__(
        self,
        entity_id: str,
        area_id: str | None = None,
        device_id: str | None = None,
    ) -> None:
        """Initialize mock entity entry."""
        self.entity_id = entity_id
        self.area_id = area_id
        self.device_id = device_id


class EntityRegistry:
    """Mock EntityRegistry class."""

    def __init__(self) -> None:
        """Initialize mock entity registry."""
        self._entities: dict[str, EntityEntry] = {}

    def async_get(self, entity_id: str) -> EntityEntry | None:
        """Get an entity by ID."""
        return self._entities.get(entity_id)


def async_get(hass: HomeAssistant) -> EntityRegistry:
    """Get the entity registry."""
    return MagicMock(spec=EntityRegistry)

