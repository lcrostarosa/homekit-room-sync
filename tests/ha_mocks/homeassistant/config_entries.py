"""Mock homeassistant.config_entries module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock


class ConfigEntry:
    """Mock ConfigEntry class."""

    def __init__(
        self,
        entry_id: str = "test_entry",
        data: dict[str, Any] | None = None,
        title: str = "Test Entry",
        version: int = 1,
    ) -> None:
        """Initialize mock config entry."""
        self.entry_id = entry_id
        self.data = data or {}
        self.title = title
        self.version = version
        self.async_on_unload = MagicMock()

    def add_update_listener(self, listener: Any) -> Any:
        """Add update listener."""
        return MagicMock()


class ConfigFlow:
    """Mock ConfigFlow class."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize mock config flow."""
        self.hass = MagicMock()

    def __init_subclass__(cls, *, domain: str | None = None, **kwargs: Any) -> None:
        """Handle subclass creation with domain argument."""
        super().__init_subclass__(**kwargs)
        if domain:
            cls._domain = domain

    def async_abort(self, reason: str) -> dict[str, Any]:
        """Abort the flow."""
        return {"type": "abort", "reason": reason}

    def async_show_form(
        self,
        step_id: str,
        data_schema: Any = None,
        errors: dict[str, str] | None = None,
        description_placeholders: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Show a form."""
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(
        self, title: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create an entry."""
        return {"type": "create_entry", "title": title, "data": data}

    def _async_current_entries(self) -> list[ConfigEntry]:
        """Get current entries."""
        return []


class OptionsFlow:
    """Mock OptionsFlow class."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize mock options flow."""
        self.config_entry = config_entry
        self.hass = MagicMock()

    def async_show_form(
        self,
        step_id: str,
        data_schema: Any = None,
        errors: dict[str, str] | None = None,
        description_placeholders: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Show a form."""
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(
        self, title: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create an entry."""
        return {"type": "create_entry", "title": title, "data": data}


# Type alias
ConfigFlowResult = dict[str, Any]

