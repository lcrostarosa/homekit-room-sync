"""Mock homeassistant.core module."""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import MagicMock


class HomeAssistant:
    """Mock Home Assistant instance."""

    def __init__(self) -> None:
        """Initialize mock Home Assistant."""
        self.data: dict[str, Any] = {}
        self.config = MagicMock()
        self.bus = MagicMock()
        self.services = MagicMock()
        self.config_entries = MagicMock()

    async def async_add_executor_job(
        self, func: Callable[..., Any], *args: Any
    ) -> Any:
        """Run a function in the executor."""
        return func(*args)


class Event:
    """Mock Event class."""

    def __init__(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Initialize mock event."""
        self.event_type = event_type
        self.data = data or {}


def callback(func: Callable[..., Any]) -> Callable[..., Any]:
    """Mock callback decorator."""
    return func

