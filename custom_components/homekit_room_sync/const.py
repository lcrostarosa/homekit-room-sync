"""Constants for the HomeKit Room Sync integration."""

from typing import Final

DOMAIN: Final = "homekit_room_sync"

# New schema keys
CONF_BRIDGES: Final = "bridges"
CONF_ENTRY_ID: Final = "entry_id"
CONF_AREAS: Final = "areas"
CONF_INCLUDE_ENTITIES: Final = "include_entities"
CONF_EXCLUDE_ENTITIES: Final = "exclude_entities"

# Legacy keys retained for migration only
CONF_BRIDGE_NAME: Final = "bridge_name"
CONF_MANAGED_BRIDGES: Final = "managed_bridges"
CONF_BRIDGE_ID: Final = "bridge_id"
CONF_BRIDGE_TITLE: Final = "bridge_title"
CONF_ALLOWED_AREAS: Final = "allowed_areas"
CONF_DEFAULT_ROOM: Final = "default_room"

# Event types to listen for
EVENT_ENTITY_REGISTRY_UPDATED: Final = "entity_registry_updated"
EVENT_AREA_REGISTRY_UPDATED: Final = "area_registry_updated"
EVENT_DEVICE_REGISTRY_UPDATED: Final = "device_registry_updated"

# Debounce delay in seconds
SYNC_DEBOUNCE_DELAY: Final = 0.5

# HomeKit service
HOMEKIT_DOMAIN: Final = "homekit"
SERVICE_RELOAD: Final = "reload"

# Services
SERVICE_SYNC: Final = "sync"

# Service attributes
ATTR_ENTRY_ID: Final = "entry_id"
ATTR_BRIDGE_ID: Final = "bridge_id"
