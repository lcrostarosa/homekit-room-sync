"""Minimal mock for homeassistant.helpers.config_validation."""

from __future__ import annotations

from collections.abc import Mapping

import voluptuous as vol


def multi_select(options: Mapping | list | set) -> vol.In:
    """Return a simplistic multi-select validator."""
    if isinstance(options, Mapping):
        choices = list(options.keys())
    else:
        choices = list(options)
    return vol.In(choices)
