# Contributing to HomeKit Room Sync

Thank you for your interest in contributing to HomeKit Room Sync! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We're all here to improve home automation together.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [Poetry](https://python-poetry.org/) for dependency management
- A Home Assistant development environment (optional, for testing)

### Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/lcrostarosa/homekit-room-sync.git
cd homekit-room-sync
```

2. **Install dependencies with Poetry**

```bash
poetry install
```

3. **Activate the virtual environment**

```bash
poetry shell
```

### Running Quality Checks

Before submitting a pull request, ensure your code passes all quality checks:

```bash
# Linting
poetry run ruff check .

# Type checking
poetry run mypy custom_components/homekit_room_sync

# Format check
poetry run ruff format --check .
```

To automatically fix formatting issues:

```bash
poetry run ruff format .
```

## How to Contribute

### Reporting Bugs

1. Check the [existing issues](https://github.com/lcrostarosa/homekit-room-sync/issues) to avoid duplicates
2. Create a new issue with:
   - A clear, descriptive title
   - Steps to reproduce the bug
   - Expected vs actual behavior
   - Home Assistant version
   - Relevant log entries (enable debug logging first)

**Enable debug logging** by adding this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.homekit_room_sync: debug
```

### Suggesting Features

1. Check existing issues for similar suggestions
2. Create a new issue with:
   - A clear description of the feature
   - Use case / why it would be useful
   - Any implementation ideas (optional)

### Submitting Pull Requests

1. **Create a branch** from `main`:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

2. **Make your changes** following the code style guidelines below

3. **Test your changes** in a Home Assistant environment if possible

4. **Commit your changes** with a clear message:

```bash
git commit -m "feat: add support for multiple default rooms"
# or
git commit -m "fix: handle missing area gracefully"
```

5. **Push and create a pull request**:

```bash
git push origin feature/your-feature-name
```

Then open a PR on GitHub with:
- A clear description of what the PR does
- Reference to any related issues
- Screenshots if applicable (for UI changes)

## Code Style Guidelines

### General

- Follow [Home Assistant development guidelines](https://developers.home-assistant.io/)
- Use async/await for all I/O operations
- Add type hints to all functions
- Write docstrings for all public methods

### Python Style

- Line length: 79 characters max
- Use double quotes for strings
- Follow PEP 8 conventions
- Use `ruff` for linting and formatting

### Example Function

```python
async def async_example_function(
    hass: HomeAssistant,
    entity_id: str,
) -> str | None:
    """Short description of what the function does.

    Longer description if needed, explaining the behavior
    in more detail.

    Args:
        hass: The Home Assistant instance.
        entity_id: The entity ID to process.

    Returns:
        The result string, or None if not found.
    """
    # Implementation here
    pass
```

### Commit Messages

Use conventional commit format:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

## Project Structure

```
homekit-room-sync/
├── custom_components/
│   └── homekit_room_sync/
│       ├── __init__.py      # Integration setup and event handling
│       ├── config_flow.py   # Configuration UI
│       ├── const.py         # Constants
│       ├── coordinator.py   # Core sync logic
│       ├── manifest.json    # Integration metadata
│       └── strings.json     # UI strings
├── hacs.json               # HACS metadata
├── pyproject.toml          # Poetry configuration
├── README.md               # User documentation
├── CONTRIBUTING.md         # This file
└── LICENSE                 # MIT License
```

## Testing

### Manual Testing

1. Copy `custom_components/homekit_room_sync` to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services
4. Test various scenarios:
   - Initial sync on startup
   - Entity area changes
   - Area renames
   - Multiple bridges

### Automated Tests

We welcome contributions to add automated tests! Create tests in a `tests/` directory using `pytest` and `pytest-asyncio`.

## Questions?

If you have questions about contributing, feel free to:

- Open a [discussion](https://github.com/lcrostarosa/homekit-room-sync/discussions) on GitHub
- Ask in an issue

Thank you for contributing!

