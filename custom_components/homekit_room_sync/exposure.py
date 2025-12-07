"""Helpers for computing HomeKit exposure plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, device_registry, entity_registry

if TYPE_CHECKING:
    from .bridge_manager import ManagedBridgeConfig


@dataclass(slots=True)
class ExposurePlan:
    """Describes the entities and rooms that should be exposed to HomeKit."""

    allowed_entities: set[str]
    include_entities: list[str]
    exclude_entities: list[str]
    rooms_by_entity: dict[str, str]


def build_exposure_plan(
    hass: HomeAssistant,
    bridge: "ManagedBridgeConfig",
) -> ExposurePlan:
    """Compute which entities should be exposed for a bridge configuration."""
    entity_reg = entity_registry.async_get(hass)
    device_reg = device_registry.async_get(hass)
    area_reg = area_registry.async_get(hass)

    allowed_entities: set[str] = set()
    rooms_by_entity: dict[str, str] = {}

    for entity in entity_reg.entities.values():
        entity_id = entity.entity_id
        area_id = _resolve_area_id(entity, device_reg)

        include = False
        if bridge.allowed_areas:
            include = bool(area_id and area_id in bridge.allowed_areas)
        else:
            include = True

        if entity_id in bridge.include_entities:
            include = True

        if entity_id in bridge.exclude_entities:
            include = False

        if not include:
            continue

        allowed_entities.add(entity_id)
        room_name = _resolve_room_name(area_id, area_reg, bridge)
        if room_name:
            rooms_by_entity[entity_id] = room_name

    return ExposurePlan(
        allowed_entities=allowed_entities,
        include_entities=sorted(allowed_entities),
        exclude_entities=sorted(bridge.exclude_entities),
        rooms_by_entity=rooms_by_entity,
    )


def _resolve_area_id(entity_entry, device_reg: device_registry.DeviceRegistry) -> str | None:
    """Resolve the most specific area_id for an entity."""
    area_id = getattr(entity_entry, "area_id", None)
    if area_id:
        return area_id

    device_id = getattr(entity_entry, "device_id", None)
    if not device_id:
        return None

    device_entry = device_reg.async_get(device_id)
    if not device_entry:
        return None

    return getattr(device_entry, "area_id", None)


def _resolve_room_name(
    area_id: str | None,
    area_reg: area_registry.AreaRegistry,
    bridge: "ManagedBridgeConfig",
) -> str | None:
    """Resolve the preferred room label for an entity."""
    if area_id:
        area = area_reg.async_get_area(area_id)
        if area and area.name:
            return str(area.name)
    return bridge.default_room
