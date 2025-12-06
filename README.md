# HomeKit Room Sync

[![Status: Pre-Alpha](https://img.shields.io/badge/Status-Pre--Alpha-red.svg)](https://github.com/lcrostarosa/homekit-room-sync)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Contributors Welcome](https://img.shields.io/badge/Contributors-Welcome-brightgreen.svg)](https://github.com/lcrostarosa/homekit-room-sync/blob/master/CONTRIBUTING.md)

> [!CAUTION]
> **This project is in active development and is NOT ready for production use.**
> 
> - Pre-alpha status: Expect breaking changes and incomplete features
> - Untested: Has not been thoroughly tested in real environments
> - Use at your own risk: May cause issues with your HomeKit setup
>
> **DISCLAIMER: This integration directly modifies internal Home Assistant storage files. YOU MUST BACK UP YOUR HOME ASSISTANT CONFIGURATION BEFORE INSTALLING OR USING THIS INTEGRATION. The authors are not responsible for any data loss or corruption.**

A Home Assistant custom integration that automatically synchronizes your Home Assistant Areas with HomeKit Room assignments.

## Why This Exists

The [HomeKit Bridge configuration](https://www.home-assistant.io/integrations/homekit#configuration) in Home Assistant has **no concept of filtering entities by Area**.

You can filter by domains (lights, switches, fans, etc.) and use wildcards, but this approach is opinionated and becomes a maintenance headache over time. Every time you add a new device, you have to think about whether it matches your existing filters.

**The problem:** You organize your smart home by rooms (Areas) in Home Assistant, but HomeKit Bridge forces you to think in terms of entity types and naming patterns. This disconnect makes configuration fragile and tedious to maintain.

**The solution:** HomeKit Room Sync bridges this gap. Organize your devices into Areas in Home Assistant, and this integration automatically syncs those room assignments to your HomeKit bridges. Add a device to an Area once, and it syncs to your Homekit Bridge.

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
4. Select a HomeKit Bridge from the dropdown (Friendly names are displayed)
5. Optionally select a default room for entities without area assignments
6. Click **Submit**

![Select Bridge](assets/select_bridge.png)
*Select the HomeKit Bridge you want to sync*

### Usage

Once configured, the integration works automatically in the background.

1. **Assign Areas in Home Assistant**: Go to **Settings > Devices & Services > Entities** and assign an **Area** to your entities (e.g., assign a Light to "Living Room").
2. **Wait for Sync**: The integration monitors these changes. After a short delay (debounced), it updates the HomeKit configuration.
3. **Check Apple Home**: Open the Home app on your iOS device. The device should now be in the corresponding Room in HomeKit.

![Apple Home Room](assets/apple_home_room.png)
*Devices automatically assigned to the correct room in Apple Home*

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
│                    Home Assistant                               │
│                                                                 │
│  ┌──────────────┐    ┌─────────────────────────┐                │
│  │ Entity/Area  │───▶│ HomeKit Room Sync       │                │
│  │ Registry     │    │ (Listens for changes)   │                │
│  └──────────────┘    └───────────┬─────────────┘                │
│                                  │                              │
│                                  ▼                              │
│                      ┌─────────────────────────┐                │
│                      │ .storage/homekit.*.state│                │
│                      │ (Updates room_name)     │                │
│                      └───────────┬─────────────┘                │
│                                  │                              │
│                                  ▼                              │
│                      ┌─────────────────────────┐                │
│                      │ homekit.reload service  │                │
│                      │ (Applies changes)       │                │
│                      └───────────┬─────────────┘                │
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

### Local Deployment via SSH

For quick development iteration, you can deploy directly to your Home Assistant server using the included deploy script.

#### Quick Start

```bash
# Deploy to a specific host
make deploy HOST=192.168.1.100

# Or use the script directly
./scripts/deploy.sh homeassistant.local
```

#### Using Environment Variables

Create a `.env` file for persistent configuration:

```bash
# Copy the example file
cp env.example .env

# Edit with your settings
nano .env
```

Example `.env` configuration:

```bash
HA_HOST=192.168.1.100
HA_USER=root
HA_SSH_PORT=22
HA_CONFIG_PATH=/config
HA_RESTART=false
```

Then simply run:

```bash
make deploy
```

#### Deploy Script Options

```bash
./scripts/deploy.sh [OPTIONS] [HOST]

Options:
  -h, --help          Show help message
  -u, --user USER     SSH user (default: root)
  -p, --port PORT     SSH port (default: 22)
  -c, --config PATH   HA config directory (default: /config)
  -r, --restart       Restart Home Assistant after deployment
  --dry-run           Show what would be done without executing
```

#### Common Configuration Paths

| Installation Type | Config Path |
|-------------------|-------------|
| HAOS / Docker | `/config` |
| Supervised | `/usr/share/hassio/homeassistant` |
| Core (venv) | `/home/homeassistant/.homeassistant` |

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Home Assistant](https://www.home-assistant.io/) for the amazing home automation platform
- [HACS](https://hacs.xyz/) for making custom integration distribution easy
