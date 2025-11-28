# HomeKit Room Sync

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration that automatically synchronizes your Home Assistant Areas with HomeKit Room assignments.

## Overview

When you expose entities to Apple HomeKit through the [HomeKit Bridge integration](https://www.home-assistant.io/integrations/homekit/), the room assignments in the Apple Home app can get out of sync with your Home Assistant area assignments. This integration solves that problem by:

1. **Monitoring Changes**: Listening for entity and area registry updates in real-time
2. **Syncing Rooms**: Automatically updating HomeKit room assignments to match your Home Assistant areas
3. **Applying Changes**: Triggering a HomeKit Bridge reload to apply the changes to the Apple Home app

## Features

- Automatic room synchronization on startup
- Real-time sync when entities or areas change
- Configurable default room for entities without area assignments
- Support for multiple HomeKit bridges
- Debounced updates to prevent excessive reloads
- Safe storage modifications with automatic backups

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/lcrostarosa/homekit-room-sync`
6. Select category: "Integration"
7. Click "Add"
8. Search for "HomeKit Room Sync" and install it
9. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/homekit_room_sync` folder from this repository
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "HomeKit Room Sync"
4. Select a HomeKit Bridge from the dropdown
5. Optionally select a default room for entities without area assignments
6. Click **Submit**

### Configuration Options

| Option | Description |
|--------|-------------|
| **HomeKit Bridge** | The HomeKit bridge to sync room assignments for |
| **Default Room** | The room to assign to entities that don't have an area in Home Assistant (optional) |

### Multiple Bridges

If you have multiple HomeKit bridges, you can add the integration multiple times, once for each bridge. Each bridge can have its own default room setting.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    Home Assistant                                │
│                                                                 │
│  ┌──────────────┐    ┌─────────────────────────┐               │
│  │ Entity/Area  │───▶│ HomeKit Room Sync       │               │
│  │ Registry     │    │ (Listens for changes)   │               │
│  └──────────────┘    └───────────┬─────────────┘               │
│                                  │                              │
│                                  ▼                              │
│                      ┌─────────────────────────┐               │
│                      │ .storage/homekit.*.state│               │
│                      │ (Updates room_name)     │               │
│                      └───────────┬─────────────┘               │
│                                  │                              │
│                                  ▼                              │
│                      ┌─────────────────────────┐               │
│                      │ homekit.reload service  │               │
│                      │ (Applies changes)       │               │
│                      └───────────┬─────────────┘               │
│                                  │                              │
└──────────────────────────────────┼──────────────────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   Apple HomeKit     │
                        │   (Updated rooms)   │
                        └─────────────────────┘
```

### Room Assignment Priority

For each entity, the room is determined in the following order:

1. **Entity's direct area**: If the entity has an area assigned directly
2. **Device's area**: If the entity's parent device has an area assigned
3. **Default room**: The configured default room for the bridge
4. **No change**: If none of the above, the room assignment is left unchanged

## Important Notes

⚠️ **Storage Modification Warning**

This integration directly modifies HomeKit Bridge storage files located in your Home Assistant `.storage` directory. While the integration creates backups before making changes, you should:

- Keep regular backups of your Home Assistant configuration
- Understand that incorrect modifications could affect your HomeKit setup
- Check the Home Assistant logs if you encounter issues

### Supported Home Assistant Versions

- Home Assistant 2024.1.0 or newer

### Known Limitations

- Changes may take a few seconds to appear in the Apple Home app after sync
- Some HomeKit apps may cache room assignments; force-close and reopen the app if changes don't appear

## Troubleshooting

### Sync Not Working

1. Check that the HomeKit Bridge integration is set up and running
2. Verify that entities are exposed to HomeKit
3. Check the Home Assistant logs for error messages

### Rooms Not Updating in Apple Home

1. Wait a few seconds for the sync to complete
2. Force-close the Apple Home app and reopen it
3. Try removing and re-adding the bridge in Apple Home (last resort)

### Enable Debug Logging

Add this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.homekit_room_sync: debug
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/lcrostarosa/homekit-room-sync.git
cd homekit-room-sync

# Install dependencies with Poetry
poetry install

# Run linting
poetry run ruff check .

# Run type checking
poetry run mypy custom_components/homekit_room_sync
```

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Home Assistant](https://www.home-assistant.io/) for the amazing home automation platform
- [HACS](https://hacs.xyz/) for making custom integration distribution easy

