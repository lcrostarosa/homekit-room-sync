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

try:  # Home Assistant runtime
    from homeassistant.data_entry_flow import FlowResultType
except Exception:  # Tests with mocks
    from enum import Enum

    class FlowResultType(Enum):
        """Fallback FlowResultType for tests."""

        FORM = "form"
        MENU = "menu"

from .bridge_manager import ManagedBridgeConfig, parse_managed_bridge_configs
from .const import (
    ATTR_ENTRY_ID,
    CONF_ALLOWED_AREAS,
    CONF_BRIDGE_ID,
    CONF_BRIDGE_NAME,
    CONF_BRIDGE_TITLE,
    CONF_DEFAULT_ROOM,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITIES,
    CONF_MANAGED_BRIDGES,
    DOMAIN,
    SERVICE_SYNC,
)
from .exposure import build_exposure_plan
from .storage import async_discover_bridges

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
        self._area_name_lookup: dict[str, str] = {}
        self._area_id_lookup: dict[str, str] = {}
        self._discovered_bridges: dict[str, str] = {}
        self._selected_bridge_ids: list[str] = []
        self._bridge_form_index = 0
        self._bridge_payloads: list[dict[str, Any]] = []
        self._existing_bridge_map: dict[str, dict[str, Any]] = {}

    async def _ensure_area_data(self) -> None:
        if self._area_options is not None:
            return

        registry = area_registry.async_get(self.hass)
        options: dict[str, str] = {}
        name_lookup: dict[str, str] = {}
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
            name_lookup[key] = label
            id_lookup[key] = area.id or key

        self._area_options = options
        self._area_name_lookup = name_lookup
        self._area_id_lookup = id_lookup

    def _area_key_for_id(self, area_id: str) -> str | None:
        for key, stored_id in self._area_id_lookup.items():
            if stored_id == area_id:
                return key
        return None

    def _build_bridge_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        area_options = dict(self._area_options or {})

        allowed_defaults: list[str] = []
        for area_id in defaults.get(CONF_ALLOWED_AREAS, []):
            key = self._area_key_for_id(area_id)
            if key is None:
                area_options[area_id] = area_id
                self._area_id_lookup[area_id] = area_id
                key = area_id
            allowed_defaults.append(key)

        room_options = {"": "(No default room)"}
        room_options.update(area_options)

        default_room_name = defaults.get(CONF_DEFAULT_ROOM)
        default_room_key = ""
        if default_room_name:
            for key, name in self._area_name_lookup.items():
                if name == default_room_name:
                    default_room_key = key
                    break
            else:
                room_options[default_room_name] = default_room_name
                self._area_name_lookup[default_room_name] = default_room_name
                default_room_key = default_room_name

        include_defaults = _list_to_text(
            defaults.get(CONF_INCLUDE_ENTITIES, []),
        )
        exclude_defaults = _list_to_text(
            defaults.get(CONF_EXCLUDE_ENTITIES, []),
        )

        return vol.Schema(
            {
                vol.Optional(
                    CONF_ALLOWED_AREAS,
                    default=allowed_defaults,
                ): cv.multi_select(area_options),
                vol.Optional(
                    CONF_DEFAULT_ROOM,
                    default=default_room_key,
                ): vol.In(room_options),
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
        friendly_name: str,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        allowed_keys = user_input.get(CONF_ALLOWED_AREAS) or []
        allowed_ids = sorted(
            {
                self._area_id_lookup.get(key, key)
                for key in allowed_keys
                if key
            }
        )

        default_room_key = user_input.get(CONF_DEFAULT_ROOM) or ""
        default_room = None
        if default_room_key:
            default_room = self._area_name_lookup.get(default_room_key)
            registry = None
            if default_room is None:
                area_id = self._area_id_lookup.get(default_room_key)
                if area_id:
                    registry = area_registry.async_get(self.hass)
                    area_entry = registry.async_get_area(area_id)
                    if area_entry and area_entry.name:
                        default_room = str(area_entry.name)
            if default_room is None:
                registry = registry or area_registry.async_get(self.hass)
                area_entry = registry.async_get_area(default_room_key)
                if area_entry and area_entry.name:
                    default_room = str(area_entry.name)
            if default_room is None:
                default_room = default_room_key

        include_entities = _parse_entity_text(
            user_input.get(CONF_INCLUDE_ENTITIES),
        )
        include_set = set(include_entities)
        exclude_entities = [
            entity
            for entity in _parse_entity_text(
                user_input.get(CONF_EXCLUDE_ENTITIES)
            )
            if entity not in include_set
        ]

        return {
            CONF_BRIDGE_ID: bridge_id,
            CONF_BRIDGE_TITLE: friendly_name,
            CONF_ALLOWED_AREAS: allowed_ids,
            CONF_DEFAULT_ROOM: default_room,
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
        friendly_name = self._discovered_bridges.get(bridge_id, bridge_id)
        defaults = self._existing_bridge_map.get(bridge_id, {})

        if user_input is not None:
            payload = self._serialize_bridge_input(
                bridge_id,
                friendly_name,
                user_input,
            )
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

    async def _finish_bridge_flow(self) -> ConfigFlowResult:
        raise NotImplementedError

    def _log_exposure_preview(self, payloads: list[dict[str, Any]]) -> None:
        """Log which entities will be exposed for each configured bridge."""
        for payload in payloads:
            config = ManagedBridgeConfig.from_dict(payload)
            plan = build_exposure_plan(self.hass, config)
            if plan.include_entities:
                sample = ", ".join(plan.include_entities[:10])
                if len(plan.include_entities) > 10:
                    sample = f"{sample}, …"
                _LOGGER.info(
                    "Preview: bridge %s will expose %d entities (%s)",
                    config.title,
                    len(plan.include_entities),
                    sample,
                )
            else:
                _LOGGER.info(
                    "Preview: bridge %s currently exposes no entities",
                    config.title,
                )


class HomeKitRoomSyncConfigFlow(
    BridgeFlowMixin, ConfigFlow, domain=DOMAIN
):  # type: ignore[call-arg]
    """Handle a config flow for HomeKit Room Sync."""

    VERSION = 2

    def __init__(self) -> None:
        ConfigFlow.__init__(self)
        BridgeFlowMixin.__init__(self)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HomeKitRoomSyncOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        discovered = await async_discover_bridges(self.hass)
        if not discovered:
            return self.async_abort(reason="no_bridges")

        configured = {
            managed.get(CONF_BRIDGE_ID)
            for entry in self._async_current_entries()
            for managed in entry.data.get(CONF_MANAGED_BRIDGES, [])
            if isinstance(managed, dict)
        }
        for entry in self._async_current_entries():
            legacy_bridge = entry.data.get(CONF_BRIDGE_NAME)
            if isinstance(legacy_bridge, str):
                configured.add(legacy_bridge)

        available = {
            bridge_id: name
            for bridge_id, name in discovered.items()
            if bridge_id not in configured
        }

        if not available:
            return self.async_abort(reason="all_bridges_configured")

        if user_input is not None:
            selected = user_input.get(CONF_MANAGED_BRIDGES, [])
            if not selected:
                errors["base"] = "select_bridge"
            else:
                self._discovered_bridges = available
                self._selected_bridge_ids = selected
                self._bridge_payloads = []
                self._bridge_form_index = 0
                self._existing_bridge_map = {}
                return await self.async_step_bridge()

        schema = vol.Schema(
            {
                vol.Required(CONF_MANAGED_BRIDGES): cv.multi_select(available),
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

    @staticmethod
    def is_matching(*_: Any, **__: Any) -> bool:
        """Return whether this flow matches a discovery (unused)."""
        return False

    async def _finish_bridge_flow(self) -> ConfigFlowResult:
        if not self._bridge_payloads:
            return self.async_abort(reason="no_bridges")

        if len(self._bridge_payloads) == 1:
            bridge_title = self._bridge_payloads[0][CONF_BRIDGE_TITLE]
            title = f"HomeKit Bridge: {bridge_title}"
        else:
            title = f"HomeKit Room Sync ({len(self._bridge_payloads)} bridges)"

        self._log_exposure_preview(self._bridge_payloads)
        return self.async_create_entry(
            title=title,
            data={CONF_MANAGED_BRIDGES: self._bridge_payloads},
        )


class HomeKitRoomSyncOptionsFlow(BridgeFlowMixin, OptionsFlow):
    """Handle options flow for HomeKit Room Sync."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._safe_options_init(config_entry)
        BridgeFlowMixin.__init__(self)

    def _safe_options_init(self, config_entry: ConfigEntry) -> None:
        """Initialize OptionsFlow while remaining compatible with test mocks."""
        try:
            OptionsFlow.__init__(self, config_entry)  # type: ignore[misc]
        except TypeError:
            # Some mock environments (and older HA versions) provide an OptionsFlow
            # base without an __init__ implementation. Fall back to storing the
            # config entry manually so tests keep working.
            self.config_entry = config_entry
            if not hasattr(self, "hass"):
                self.hass = getattr(config_entry, "hass", None)

    def _show_menu(self, **kwargs: Any) -> ConfigFlowResult:
        """Show a menu, using HA's helper when available."""
        try:
            return super().async_show_menu(**kwargs)  # type: ignore[attr-defined]
        except AttributeError:
            return {
                "type": FlowResultType.MENU,
                "step_id": kwargs.get("step_id", "init"),
                "menu_options": kwargs.get("menu_options", []),
                "description_placeholders": kwargs.get(
                    "description_placeholders", {}
                ),
            }

    def async_show_menu(self, *args: Any, **kwargs: Any) -> ConfigFlowResult:
        """Return a menu result (compat shim for tests and HA)."""
        step_id = kwargs.get("step_id") or (args[0] if args else "init")
        menu_options = kwargs.get("menu_options") or (
            args[1] if len(args) > 1 else []
        )
        description_placeholders = kwargs.get("description_placeholders") or {}
        return {
            "type": FlowResultType.MENU,
            "step_id": step_id,
            "menu_options": menu_options,
            "description_placeholders": description_placeholders,
        }

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        if user_input is not None:
            next_step = user_input.get("next_step_id")
            if next_step == "configure":
                return await self.async_step_configure()
            if next_step == "resync":
                return await self.async_step_resync()

        return self._show_menu(
            step_id="init",
            menu_options=["configure", "resync"],
        )

    async def async_step_configure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        discovered = await async_discover_bridges(self.hass)
        current_configs = [
            managed
            for managed in self.config_entry.data.get(CONF_MANAGED_BRIDGES, [])
            if isinstance(managed, dict)
        ]
        current_ids = [
            managed.get(CONF_BRIDGE_ID)
            for managed in current_configs
            if isinstance(managed.get(CONF_BRIDGE_ID), str)
        ]

        other_entries = [
            entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id != self.config_entry.entry_id
        ]
        reserved_ids = {
            managed.get(CONF_BRIDGE_ID)
            for entry in other_entries
            for managed in entry.data.get(CONF_MANAGED_BRIDGES, [])
            if isinstance(managed, dict)
        }

        available = {
            bridge_id: name
            for bridge_id, name in discovered.items()
            if bridge_id not in reserved_ids or bridge_id in current_ids
        }

        # Ensure currently configured bridges remain selectable even if missing
        for bridge_id in current_ids:
            if bridge_id and bridge_id not in available:
                available[bridge_id] = next(
                    (
                        cfg.get(CONF_BRIDGE_TITLE)
                        for cfg in current_configs
                        if cfg.get(CONF_BRIDGE_ID) == bridge_id
                    ),
                    bridge_id,
                )

        if user_input is not None:
            selected = user_input.get(CONF_MANAGED_BRIDGES, [])
            if not selected:
                errors["base"] = "select_bridge"
            else:
                self._discovered_bridges = available
                self._selected_bridge_ids = selected
                self._bridge_payloads = []
                self._bridge_form_index = 0
                self._existing_bridge_map = {
                    cfg.get(CONF_BRIDGE_ID): cfg for cfg in current_configs
                }
                return await self.async_step_bridge()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MANAGED_BRIDGES,
                    default=current_ids,
                ): cv.multi_select(available),
            }
        )
        return self.async_show_form(
            step_id="configure",
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
            **self.config_entry.data,
            CONF_MANAGED_BRIDGES: self._bridge_payloads,
        }
        self._log_exposure_preview(self._bridge_payloads)
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
        )
        return self.async_create_entry(title="", data={})

    async def async_step_resync(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        bridge_configs = parse_managed_bridge_configs(self.config_entry)
        if not bridge_configs:
            return self.async_abort(reason="no_bridges")

        if user_input is None:
            summaries: list[str] = []
            for config in bridge_configs:
                plan = build_exposure_plan(self.hass, config)
                preview = ", ".join(plan.include_entities[:5])
                if len(plan.include_entities) > 5:
                    preview = f"{preview}, …"
                summaries.append(
                    f"{config.title}: {len(plan.include_entities)} entities"
                    f"{f' ({preview})' if preview else ''}"
                )

            summary = (
                "\n".join(summaries) if summaries else "No entities to expose."
            )

            return self.async_show_form(
                step_id="resync",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "summary": summary,
                },
            )

        if domain_data := self.hass.data.get(DOMAIN):
            if entry_data := domain_data.get(self.config_entry.entry_id):
                manager = entry_data.get("manager")
                if manager is not None:
                    await manager.async_sync()
                    return self.async_create_entry(title="", data={})

        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SYNC,
            {ATTR_ENTRY_ID: self.config_entry.entry_id},
            blocking=True,
        )
        return self.async_create_entry(title="", data={})
