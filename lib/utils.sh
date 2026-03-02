#!/usr/bin/env zsh
# lib/utils.sh - Unified utilities loader
# Loads all utility modules

# ── Load Colors ──────────────────────────────────────────
source "${${(%):-%x}:A:h}/utils/colors.sh"

# ── Load Logging ─────────────────────────────────────────
source "${${(%):-%x}:A:h}/utils/logging.sh"

# ── Load Helpers ──────────────────────────────────────────
source "${${(%):-%x}:A:h}/utils/helpers.sh"

# ── Version ───────────────────────────────────────────────
get_vibe_version() {
    local vfile="${VIBE_ROOT:-$(cd "$(dirname "${(%):-%x}")/.." && pwd)}/VERSION"
    [[ -f "$vfile" ]] && cat "$vfile" || echo "2.0.0-dev"
}
