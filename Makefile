.PHONY: help install lint format typecheck check clean dev test

# Default target
help:
	@echo "HomeKit Room Sync - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup:"
	@echo "  install     Install dependencies with Poetry"
	@echo "  dev         Install dependencies and set up dev environment"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint        Run Ruff linter"
	@echo "  format      Format code with Ruff"
	@echo "  typecheck   Run mypy type checker"
	@echo "  check       Run all checks (lint + typecheck)"
	@echo ""
	@echo "Testing:"
	@echo "  test        Run pytest"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean       Remove build artifacts and caches"
	@echo "  bump-patch  Bump patch version (0.0.x)"
	@echo "  bump-minor  Bump minor version (0.x.0)"
	@echo "  bump-major  Bump major version (x.0.0)"

# Install dependencies
install:
	poetry install

# Set up development environment
dev: install
	@echo "Development environment ready!"
	@echo "Run 'poetry shell' to activate the virtual environment"

# Run linter
lint:
	poetry run ruff check custom_components/

# Format code
format:
	poetry run ruff format custom_components/
	poetry run ruff check --fix custom_components/

# Run type checker
typecheck:
	poetry run mypy custom_components/homekit_room_sync

# Run all checks
check: lint typecheck
	@echo "All checks passed!"

# Run tests
test:
	poetry run pytest tests/ -v

# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Cleaned up build artifacts"

# Version bumping helpers
bump-patch:
	@current=$$(jq -r '.version' custom_components/homekit_room_sync/manifest.json); \
	major=$$(echo $$current | cut -d. -f1); \
	minor=$$(echo $$current | cut -d. -f2); \
	patch=$$(echo $$current | cut -d. -f3); \
	new="$$major.$$minor.$$((patch + 1))"; \
	jq ".version = \"$$new\"" custom_components/homekit_room_sync/manifest.json > tmp.json && mv tmp.json custom_components/homekit_room_sync/manifest.json; \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new\"/" pyproject.toml && rm -f pyproject.toml.bak; \
	echo "Bumped version: $$current -> $$new"

bump-minor:
	@current=$$(jq -r '.version' custom_components/homekit_room_sync/manifest.json); \
	major=$$(echo $$current | cut -d. -f1); \
	minor=$$(echo $$current | cut -d. -f2); \
	new="$$major.$$((minor + 1)).0"; \
	jq ".version = \"$$new\"" custom_components/homekit_room_sync/manifest.json > tmp.json && mv tmp.json custom_components/homekit_room_sync/manifest.json; \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new\"/" pyproject.toml && rm -f pyproject.toml.bak; \
	echo "Bumped version: $$current -> $$new"

bump-major:
	@current=$$(jq -r '.version' custom_components/homekit_room_sync/manifest.json); \
	major=$$(echo $$current | cut -d. -f1); \
	new="$$((major + 1)).0.0"; \
	jq ".version = \"$$new\"" custom_components/homekit_room_sync/manifest.json > tmp.json && mv tmp.json custom_components/homekit_room_sync/manifest.json; \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new\"/" pyproject.toml && rm -f pyproject.toml.bak; \
	echo "Bumped version: $$current -> $$new"

