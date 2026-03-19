"""Shared console instance for all UI output.

Uses rich.Console with force_terminal=None so rich auto-detects TTY.
- TTY (human): full color + markup
- Non-TTY (pipe / agent): plain text, no ANSI, no box chars
"""

from rich.console import Console

# highlight=False 避免 rich 对数字/路径自动着色干扰 agent 解析
console = Console(highlight=False)
