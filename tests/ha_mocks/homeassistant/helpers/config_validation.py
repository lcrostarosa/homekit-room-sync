"""Mock subset of homeassistant.helpers.config_validation."""

from __future__ import annotations

from typing import Iterable

import voluptuous as vol


def multi_select(_options: dict[str, str] | None = None):  # noqa: D401
    """Return a validator that coerces to a list of strings."""

    def validate(value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, Iterable):
            return [str(item) for item in value]
        raise vol.Invalid("Invalid multi_select value")

    return validate
