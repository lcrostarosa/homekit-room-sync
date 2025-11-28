"""Constants for the HomeKit Room Sync integration."""

from typing import Final

# Integration domain
DOMAIN: Final = "homekit_room_sync"

# Configuration keys
CONF_BRIDGE_NAME: Final = "bridge_name"
CONF_DEFAULT_ROOM: Final = "default_room"

# HomeKit storage patterns
HOMEKIT_STORAGE_PREFIX: Final = "homekit."
HOMEKIT_STORAGE_SUFFIX: Final = ".state"

# Event types to listen for
EVENT_ENTITY_REGISTRY_UPDATED: Final = "entity_registry_updated"
EVENT_AREA_REGISTRY_UPDATED: Final = "area_registry_updated"

# Debounce delay in seconds
SYNC_DEBOUNCE_DELAY: Final = 0.5

# HomeKit service
HOMEKIT_DOMAIN: Final = "homekit"
SERVICE_RELOAD: Final = "reload"

# Storage keys used in HomeKit state files
STORAGE_KEY_ACCESSORIES: Final = "accessories"
STORAGE_KEY_ENTITY_ID: Final = "entity_id"
STORAGE_KEY_ROOM_NAME: Final = "room_name"
