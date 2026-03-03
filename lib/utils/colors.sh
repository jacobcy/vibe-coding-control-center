#!/usr/bin/env zsh
# lib/utils/colors.sh - Color and formatting utilities
# Target: ~15 lines | Pure functions, no side effects

# ── Colors ──────────────────────────────────────────────
# Use printf to ensure literal escape characters are assigned
export RED=$(printf '\033[0;31m')
export GREEN=$(printf '\033[0;32m')
export YELLOW=$(printf '\033[1;33m')
export BLUE=$(printf '\033[0;34m')
export CYAN=$(printf '\033[0;36m')
export BOLD=$(printf '\033[1m')
export NC=$(printf '\033[0m')
