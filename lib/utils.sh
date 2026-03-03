#!/usr/bin/env zsh
# lib/utils.sh - Unified utilities loader
# Loads all utility modules

# shellcheck disable=SC2298
# (Zsh-specific nested parameter expansion is valid in Zsh)

# ── Determine Script Directory (Bash/Zsh compatible) ───────
# Get the directory where this script is located
if [[ -n "$ZSH_VERSION" ]]; then
    # Zsh: use Zsh-specific syntax
    _utils_script_dir="${${(%):-%x}:A:h}"
else
    # Bash: use BASH_SOURCE
    _utils_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

# ── Load Colors ──────────────────────────────────────────
source "$_utils_script_dir/utils/colors.sh"

# ── Load Logging ─────────────────────────────────────────
source "$_utils_script_dir/utils/logging.sh"

# ── Load Helpers ──────────────────────────────────────────
source "$_utils_script_dir/utils/helpers.sh"

# ── Version ───────────────────────────────────────────────
get_vibe_version() {
    local vfile="${VIBE_ROOT:-$(cd "$(dirname "${(%):-%x}")/.." && pwd)}/VERSION"
    [[ -f "$vfile" ]] && cat "$vfile" || echo "2.0.0-dev"
}
