"""Mock homeassistant.helpers.event module."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from ..core import HomeAssistant


def async_call_later(
    _hass: HomeAssistant,
    _delay: float,
    _action: Callable[..., Any],
) -> Callable[[], None]:
    """Schedule a callback after a delay."""
    return MagicMock()

