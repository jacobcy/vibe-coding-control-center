"""Shared console instance for all UI output.

Uses rich.Console with force_terminal=True to always render colors
even when output is piped or captured (e.g., by Claude Code).
- TTY (human): full color + markup
- Non-TTY (pipe): still shows colors for better readability
"""

from rich.console import Console

# force_terminal=True ensures colors work even in piped output
# highlight=False 避免 rich 对数字/路径自动着色干扰 agent 解析
console = Console(force_terminal=True, highlight=False)
