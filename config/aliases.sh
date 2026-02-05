#!/bin/bash
# Vibe Coding Aliases
# Sourced by install scripts to provide unified shortcuts.

# Determine the script directory dynamically
# This allows the aliases to work regardless of where the project is located
VIBE_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ================= Claude Code =================
alias c="claude"
alias ca="claude ask"
alias cp="claude 'create a plan for'"
alias cr="claude 'review the changes'"

# ================= OpenCode =================
alias o="opencode"
alias oa="opencode ask"

# ================= Vibecoding Control =================
# Quick access to the control center
alias vibe="bash \"$VIBE_SCRIPTS_DIR/scripts/vibecoding.sh\""

# ================= Project Init =================
alias ignition="bash \"$VIBE_SCRIPTS_DIR/install/init-project.sh\""
