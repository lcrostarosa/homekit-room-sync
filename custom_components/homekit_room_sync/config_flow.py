"""Config flow for HomeKit Room Sync integration."""

from __future__ import annotations

import logging
from typing import Any, Iterable

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import area_registry, config_validation as cv

from .const import (
    CONF_AREAS,
    CONF_BRIDGES,
    CONF_ENTRY_ID,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITIES,
    DOMAIN,
    HOMEKIT_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _parse_entity_text(value: Any) -> list[str]:
    """Normalize user-entered entity lists."""
    if value is None:
        return []
    if isinstance(value, list):
        source = ",".join(str(item) for item in value)
    else:
        source = str(value)
    parts = {part.strip() for part in source.replace("\n", ",").split(",")}
    return sorted(part for part in parts if part)


def _list_to_text(values: Iterable[str]) -> str:
    entries = sorted({val for val in values if val})
    return "\n".join(entries)


class BridgeFlowMixin:
    """Shared helpers for config and options flows."""

    def __init__(self) -> None:
        self._area_options: dict[str, str] | None = None
        self._area_id_lookup: dict[str, str] = {}
        self._homekit_titles: dict[str, str] = {}
        self._selected_bridge_ids: list[str] = []
        self._bridge_form_index = 0
        self._bridge_payloads: list[dict[str, Any]] = []
        self._existing_bridge_map: dict[str, dict[str, Any]] = {}

    async def _ensure_area_data(self) -> None:
        if self._area_options is not None:
            return

        registry = area_registry.async_get(self.hass)
        options: dict[str, str] = {}
        id_lookup: dict[str, str] = {}

        for area in sorted(
            registry.async_list_areas(),
            key=lambda area: (area.name or "").lower(),
        ):
            key = area.id or area.name
            if not key:
                continue
            label = area.name or key
            options[key] = label
            id_lookup[key] = area.id or key

        self._area_options = options
        self._area_id_lookup = id_lookup

    def _area_key_for_id(self, area_id: str) -> str | None:
        for key, stored_id in self._area_id_lookup.items():
            if stored_id == area_id:
                return key
        return None

    def _build_bridge_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        area_options = dict(self._area_options or {})

        allowed_defaults: list[str] = []
        for area_id in defaults.get(CONF_AREAS, []):
            key = self._area_key_for_id(area_id)
            if key is None:
                area_options[area_id] = area_id
                self._area_id_lookup[area_id] = area_id
                key = area_id
            allowed_defaults.append(key)

        include_defaults = _list_to_text(defaults.get(CONF_INCLUDE_ENTITIES, []))
        exclude_defaults = _list_to_text(defaults.get(CONF_EXCLUDE_ENTITIES, []))

        return vol.Schema(
            {
                vol.Optional(
                    CONF_AREAS,
                    default=allowed_defaults,
                ): cv.multi_select(area_options),
                vol.Optional(
                    CONF_INCLUDE_ENTITIES,
                    default=include_defaults,
                ): str,
                vol.Optional(
                    CONF_EXCLUDE_ENTITIES,
                    default=exclude_defaults,
                ): str,
            }
        )

    def _serialize_bridge_input(
        self,
        bridge_id: str,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        allowed_keys = user_input.get(CONF_AREAS) or []
        allowed_ids = sorted(
            {
                self._area_id_lookup.get(key, key)
                for key in allowed_keys
                if key
            }
        )

        include_entities = _parse_entity_text(user_input.get(CONF_INCLUDE_ENTITIES))
        include_set = set(include_entities)
        exclude_entities = [
            entity
            for entity in _parse_entity_text(user_input.get(CONF_EXCLUDE_ENTITIES))
            if entity not in include_set
        ]

        return {
            CONF_ENTRY_ID: bridge_id,
            CONF_AREAS: allowed_ids,
            CONF_INCLUDE_ENTITIES: include_entities,
            CONF_EXCLUDE_ENTITIES: exclude_entities,
        }

    async def _async_handle_bridge_step(
        self,
        step_id: str,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        if not self._selected_bridge_ids:
            return await self._finish_bridge_flow()

        await self._ensure_area_data()

        bridge_id = self._selected_bridge_ids[self._bridge_form_index]
        friendly_name = self._homekit_titles.get(bridge_id, bridge_id)
        defaults = self._existing_bridge_map.get(bridge_id, {})

        if user_input is not None:
            payload = self._serialize_bridge_input(bridge_id, user_input)
            self._bridge_payloads.append(payload)
            self._bridge_form_index += 1

            if self._bridge_form_index >= len(self._selected_bridge_ids):
                return await self._finish_bridge_flow()

            return await self._async_handle_bridge_step(step_id)

        schema = self._build_bridge_schema(defaults)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            description_placeholders={
                "bridge_name": friendly_name,
                "current_index": str(self._bridge_form_index + 1),
                "bridge_total": str(len(self._selected_bridge_ids)),
            },
        )

    async def _finish_bridge_flow(self) -> ConfigFlowResult:  # pragma: no cover - overridden
        raise NotImplementedError


class HomeKitRoomSyncConfigFlow(
    BridgeFlowMixin, ConfigFlow, domain=DOMAIN
):  # type: ignore[call-arg]
    """Handle a config flow for HomeKit Room Sync."""

    VERSION = 3

    def __init__(self) -> None:
        ConfigFlow.__init__(self)
        BridgeFlowMixin.__init__(self)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HomeKitRoomSyncOptionsFlow(config_entry)

    def _discover_homekit_bridges(self) -> dict[str, str]:
        entries = self.hass.config_entries.async_entries(HOMEKIT_DOMAIN)
        return {
            entry.entry_id: entry.title
            or entry.data.get("name")
            or entry.entry_id
            for entry in entries
        }

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        discovered = self._discover_homekit_bridges()
        if not discovered:
            return self.async_abort(reason="no_bridges")

        configured = {
            managed.get(CONF_ENTRY_ID)
            for entry in self._async_current_entries()
            for managed in entry.data.get(CONF_BRIDGES, [])
            if isinstance(managed, dict)
            and isinstance(managed.get(CONF_ENTRY_ID), str)
        }

        available = {
            entry_id: name
            for entry_id, name in discovered.items()
            if entry_id not in configured
        }

        if not available:
            return self.async_abort(reason="all_bridges_configured")

        if user_input is not None:
            selected = user_input.get(CONF_BRIDGES, [])
            if not selected:
                errors["base"] = "select_bridge"
            elif any(entry_id not in available for entry_id in selected):
                errors["base"] = "invalid_bridge"
            else:
                self._homekit_titles = discovered
                self._selected_bridge_ids = selected
                self._bridge_payloads = []
                self._bridge_form_index = 0
                self._existing_bridge_map = {}
                return await self.async_step_bridge()

        schema = vol.Schema(
            {
                vol.Required(CONF_BRIDGES): cv.multi_select(available),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "bridge_count": str(len(available)),
            },
        )

    async def async_step_bridge(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        return await self._async_handle_bridge_step("bridge", user_input)

    async def _finish_bridge_flow(self) -> ConfigFlowResult:
        if not self._bridge_payloads:
            return self.async_abort(reason="no_bridges")

        title = (
            f"HomeKit Bridge: {self._homekit_titles.get(self._bridge_payloads[0][CONF_ENTRY_ID], self._bridge_payloads[0][CONF_ENTRY_ID])}"
            if len(self._bridge_payloads) == 1
            else f"HomeKit Room Sync ({len(self._bridge_payloads)} bridges)"
        )

        return self.async_create_entry(
            title=title,
            data={CONF_BRIDGES: self._bridge_payloads},
        )


class HomeKitRoomSyncOptionsFlow(BridgeFlowMixin, OptionsFlow):
    """Handle options flow for HomeKit Room Sync."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        BridgeFlowMixin.__init__(self)

    def _discover_homekit_bridges(self) -> dict[str, str]:
        entries = self.hass.config_entries.async_entries(HOMEKIT_DOMAIN)
        return {
            entry.entry_id: entry.title
            or entry.data.get("name")
            or entry.entry_id
            for entry in entries
        }

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        discovered = self._discover_homekit_bridges()
        current_configs = [
            managed
            for managed in self._config_entry.data.get(CONF_BRIDGES, [])
            if isinstance(managed, dict)
        ]
        current_ids = [
            managed.get(CONF_ENTRY_ID)
            for managed in current_configs
            if isinstance(managed.get(CONF_ENTRY_ID), str)
        ]

        other_entries = [
            entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id != self._config_entry.entry_id
        ]
        reserved_ids = {
            managed.get(CONF_ENTRY_ID)
            for entry in other_entries
            for managed in entry.data.get(CONF_BRIDGES, [])
            if isinstance(managed, dict)
        }

        available = {
            entry_id: discovered.get(entry_id, entry_id)
            for entry_id in discovered
            if entry_id not in reserved_ids or entry_id in current_ids
        }

        for entry_id in current_ids:
            if entry_id not in available:
                available[entry_id] = discovered.get(entry_id, entry_id)

        if user_input is not None:
            selected = user_input.get(CONF_BRIDGES, [])
            if not selected:
                errors["base"] = "select_bridge"
            elif any(entry_id not in available for entry_id in selected):
                errors["base"] = "invalid_bridge"
            else:
                self._homekit_titles = {**discovered, **available}
                self._selected_bridge_ids = selected
                self._bridge_payloads = []
                self._bridge_form_index = 0
                self._existing_bridge_map = {
                    cfg.get(CONF_ENTRY_ID): cfg for cfg in current_configs
                }
                return await self.async_step_bridge()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BRIDGES,
                    default=current_ids,
                ): cv.multi_select(available),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "bridge_count": str(len(available)),
            },
        )

    async def async_step_bridge(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        return await self._async_handle_bridge_step("bridge", user_input)

    async def _finish_bridge_flow(self) -> ConfigFlowResult:
        new_data = {
            **self._config_entry.data,
            CONF_BRIDGES: self._bridge_payloads,
        }
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data=new_data,
        )
        return self.async_create_entry(title="", data={})
