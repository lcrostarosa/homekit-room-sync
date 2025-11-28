"""Config flow for HomeKit Room Sync integration.

This module provides the configuration UI for setting up and
managing HomeKit Room Sync bridge configurations.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar

from .const import CONF_BRIDGE_NAME, CONF_DEFAULT_ROOM, DOMAIN
from .coordinator import HomeKitRoomSyncCoordinator

_LOGGER = logging.getLogger(__name__)


class HomeKitRoomSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomeKit Room Sync.

    This config flow guides the user through selecting a HomeKit bridge
    and optionally setting a default room for entities without areas.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._bridge_name: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler.

        Args:
            config_entry: The config entry to get options for.

        Returns:
            The options flow handler.
        """
        return HomeKitRoomSyncOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - select a HomeKit bridge.

        This step presents the user with a list of available HomeKit
        bridges discovered from the storage directory.

        Args:
            user_input: User-provided form data.

        Returns:
            The next step or an error if validation fails.
        """
        errors: dict[str, str] = {}

        # Get available bridges
        bridges = await self.hass.async_add_executor_job(
            HomeKitRoomSyncCoordinator.get_available_bridges, self.hass
        )

        if not bridges:
            return self.async_abort(reason="no_bridges")

        # Check for already configured bridges
        configured_bridges = {
            entry.data[CONF_BRIDGE_NAME]
            for entry in self._async_current_entries()
        }
        available_bridges = [b for b in bridges if b not in configured_bridges]

        if not available_bridges:
            return self.async_abort(reason="all_bridges_configured")

        if user_input is not None:
            self._bridge_name = user_input[CONF_BRIDGE_NAME]

            # Validate the bridge exists
            if self._bridge_name not in available_bridges:
                errors[CONF_BRIDGE_NAME] = "invalid_bridge"
            else:
                # Move to room selection step
                return await self.async_step_room()

        # Build the form schema
        schema = vol.Schema(
            {
                vol.Required(CONF_BRIDGE_NAME): vol.In(available_bridges),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "bridge_count": str(len(available_bridges))
            },
        )

    async def async_step_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the room selection step.

        This step allows the user to select a default room for entities
        that don't have an assigned area in Home Assistant.

        Args:
            user_input: User-provided form data.

        Returns:
            The created config entry or an error.
        """
        errors: dict[str, str] = {}

        # Get available areas/rooms
        area_registry = ar.async_get(self.hass)
        areas = {
            area.name: area.name
            for area in area_registry.async_list_areas()
        }

        # Add "None" option for no default room
        room_options = {"": "(No default room)"} | areas

        if user_input is not None:
            default_room = user_input.get(CONF_DEFAULT_ROOM) or None

            # Create the config entry
            return self.async_create_entry(
                title=f"HomeKit Bridge: {self._bridge_name}",
                data={
                    CONF_BRIDGE_NAME: self._bridge_name,
                    CONF_DEFAULT_ROOM: default_room,
                },
            )

        # Build the form schema
        schema = vol.Schema(
            {
                vol.Optional(CONF_DEFAULT_ROOM, default=""): vol.In(
                    room_options
                ),
            }
        )

        return self.async_show_form(
            step_id="room",
            data_schema=schema,
            errors=errors,
            description_placeholders={"bridge_name": self._bridge_name},
        )


class HomeKitRoomSyncOptionsFlow(OptionsFlow):
    """Handle options flow for HomeKit Room Sync.

    This options flow allows users to modify the default room
    assignment after initial configuration.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow.

        Args:
            config_entry: The config entry to modify.
        """
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options form.

        Args:
            user_input: User-provided form data.

        Returns:
            The updated options or form to display.
        """
        errors: dict[str, str] = {}

        # Get available areas/rooms
        area_registry = ar.async_get(self.hass)
        areas = {
            area.name: area.name
            for area in area_registry.async_list_areas()
        }

        # Add "None" option for no default room
        room_options = {"": "(No default room)"} | areas

        if user_input is not None:
            default_room = user_input.get(CONF_DEFAULT_ROOM) or None

            # Update the config entry data
            new_data = {
                **self.config_entry.data,
                CONF_DEFAULT_ROOM: default_room
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            return self.async_create_entry(title="", data={})

        # Get current default room
        current_default = self.config_entry.data.get(CONF_DEFAULT_ROOM) or ""

        # Build the form schema
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DEFAULT_ROOM, default=current_default
                ): vol.In(room_options),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "bridge_name": self.config_entry.data[CONF_BRIDGE_NAME]
            },
        )
