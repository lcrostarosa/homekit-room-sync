"""Mock homeassistant.helpers.event module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from ..core import HomeAssistant


def async_call_later(
    hass: HomeAssistant,
    delay: float,
    action: Callable[..., Any],
) -> Callable[[], None]:
    """Schedule a callback after a delay."""
    return MagicMock()

