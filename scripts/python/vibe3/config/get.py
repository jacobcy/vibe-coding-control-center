#!/usr/bin/env python3
"""CLI command to get configuration values.

Usage:
    python -m vibe3.config.get <config_path> [--config path/to/config.yaml]
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.config.loader import load_config


def get_config_value(path: str, config_path: Path | None = None) -> Any:
    """Get a configuration value by dot-separated path.

    Args:
        path: Dot-separated path like "code_limits.v3_python.total_loc"
        config_path: Optional path to config file

    Returns:
        Configuration value

    Raises:
        SystemExit: If path is invalid
    """
    config = load_config(config_path)
    parts = path.split(".")

    obj = config
    for part in parts:
        try:
            obj = getattr(obj, part)
        except AttributeError:
            print(f"Error: Invalid config path '{path}'", file=sys.stderr)
            sys.exit(1)

    return obj


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Get configuration value by path",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  code_limits.v3_python.total_loc
  code_limits.v2_shell.total_loc
  quality.test_coverage.services""",
    )
    parser.add_argument("path", help="Dot-separated config path")
    parser.add_argument(
        "--config", "-c", type=Path, help="Path to config file (optional)"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress log output"
    )

    args = parser.parse_args()

    # Suppress logs if quiet mode
    if args.quiet:
        logger.remove()

    value = get_config_value(args.path, args.config)
    print(value)


if __name__ == "__main__":
    main()
