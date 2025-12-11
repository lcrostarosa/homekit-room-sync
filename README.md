# ha-config-exporter

`ha-config-exporter` is a **read-only** command line tool that snapshots a Home Assistant
configuration into a deterministic `config_export/` folder. The goal is to produce clean
Git-friendly YAML so configuration churn is obvious and reviewable.

## Features

- Pulls data from the Home Assistant REST API, `/config` YAML, and `.storage` JSON files
- Deterministic YAML renderer (2-space indent, ordered keys, null-stripping)
- Incremental writes and dry-run diff preview for clean Git diffs
- Modular exporter system (`automations`, `scripts`, `scenes`, `helpers`, `entities`, ...)
- Directory scaffold that always matches the expected Supervisor share layout
- Supervisor add-on manifest (optional) for easy deployment inside Home Assistant OS

## Installation

```bash
pip install .
# or with Poetry
poetry install
```

This project targets Python 3.11+.

## Usage

```bash
ha-export \
  --ha-url http://homeassistant.local:8123 \
  --token YOUR_LONG_LIVED_TOKEN \
  --config-dir /config \
  --output ./config_export \
  --incremental
```

### CLI flags

| Flag | Description |
| --- | --- |
| `--ha-url` | Home Assistant base URL (required for automations exporter) |
| `--token` | Long-lived token paired with `--ha-url` |
| `--config-dir` | Path to HA config folder (default `/config`) |
| `--output` | Destination folder (must match `config_export` structure) |
| `--incremental` | Only rewrite when file contents differ |
| `--dry-run` | Show unified diffs without writing |
| `--include/--exclude` | Comma separated exporter names to run or skip |
| `--verbose/--quiet` | Adjust log verbosity |

### Deterministic YAML rules

- 2-space indentation with `yaml.safe_dump`
- Key order: `id`, `alias`, `description`, `trigger`, `condition`, `action`, `mode`, then alphabetical
- `null` / empty dict / empty list values removed
- Home Assistant UI metadata (`metadata`, `ui_metadata`, `trace`, etc.) stripped
- Lists rendered in block style for readability

### Exported directory tree

```
config_export/
  automations/
  scripts/
  scenes/
  helpers/
  lights/
  entities/
  areas/
  dashboards/
  metadata.json
```

The MVP implements automated exporters for **automations, scripts, scenes, helpers, and the entity
registry snapshot**. Light groups, area/device topology, and dashboards have stubs in place and are
next on the roadmap.

## Architecture

```
src/ha_export/
  cli.py             # argparse CLI wiring
  main.py            # run loop, exporter orchestration, metadata handling
  models.py          # shared ExportContext dataclass
  utils/
    api.py           # Home Assistant REST helper
    fs.py            # file IO, safe writes, slug generation
    yaml.py          # deterministic normalization + dumper
  exporters/
    base.py          # abstract exporter contract
    automations.py   # REST-backed fetch of automation configs
    scripts.py       # scripts.yaml or script.* storage
    scenes.py        # scene.storage entries
    helpers.py       # input_* helpers
    entities.py      # core.entity_registry snapshot
    lights.py        # placeholder for light groups
    areas.py         # placeholder for area/device mapping
    dashboards.py    # placeholder for Lovelace dashboards
```

Each exporter implements `discover`, `export`, and `output_path` so new data sources can be added
without touching the CLI.

## Testing

Pytest fixtures mimic a `/config` tree with `.storage` files. The tests assert deterministic output
and API interactions.

```bash
poetry run pytest
```

CI hooks can later enforce `ruff` and `mypy` once the roadmap items land.

## Supervisor add-on (optional)

A starter add-on manifest is available at `addon/config.yaml` for deploying the exporter inside
Home Assistant OS. Point the `output_dir` option to a writable share, e.g. `/share/ha-export`.

## Roadmap

- Implement remaining exporters (light groups, area/device topology, dashboards)
- Add richer filtering (per-entity patterns, tag selectors)
- Wire automated publishing to HACS once exporters are complete
- Bundle binary builds for Linux containers and Supervisor add-on images
