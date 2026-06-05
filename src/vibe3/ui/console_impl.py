"""Shared console instance for all UI output.

Uses rich.Console with default TTY auto-detection.
- TTY (human): full color + markup
- Non-TTY (pipe/agent): plain text, no ANSI, no box chars
"""

from rich.console import Console

# Default TTY auto-detection - Rich will:
# - Emit ANSI colors/markup when TTY (human)
# - Emit plain text when non-TTY (pipe/agent)
console = Console(highlight=False)
