from __future__ import annotations

import argparse
import sys

from ha_export.main import run_export


def _split_list(values: list[str] | None) -> list[str]:
    names: list[str] = []
    if not values:
        return names
    for value in values:
        for part in value.split(","):
            clean = part.strip()
            if clean:
                names.append(clean.lower())
    return names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ha-export",
        description="Export Home Assistant configuration to deterministic YAML files.",
    )
    parser.add_argument("--ha-url", help="Home Assistant base URL", default=None)
    parser.add_argument("--token", help="Home Assistant long-lived token", default=None)
    parser.add_argument(
        "--config-dir",
        default="/config",
        help="Path to the Home Assistant configuration directory",
    )
    parser.add_argument(
        "--output",
        default="./config_export",
        help="Destination folder for exported artifacts",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only rewrite files whose contents changed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
    )
    parser.add_argument(
        "--include",
        action="append",
        metavar="NAMES",
        help="Comma separated exporter names to include",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        metavar="NAMES",
        help="Comma separated exporter names to skip",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit debug output",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-critical output",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    include = _split_list(args.include)
    exclude = _split_list(args.exclude)

    run_export(
        ha_url=args.ha_url,
        token=args.token,
        config_dir=args.config_dir,
        output_dir=args.output,
        incremental=args.incremental,
        dry_run=args.dry_run,
        include=include,
        exclude=exclude,
        verbose=args.verbose,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
