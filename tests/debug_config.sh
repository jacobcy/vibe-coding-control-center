#!/usr/bin/env zsh
# Debug script to test VIBE_ROOT resolution

# Mock source location logic by creating a wrapper that sources lib/config.sh
# Because lib/config.sh uses ${(%):-%x} which depends on how it's sourced.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_CONFIG="$SCRIPT_DIR/../lib/config.sh"

echo "Sourcing lib/config.sh from: $LIB_CONFIG"

# We need to source it in a way that preserves the file path for ${(%):-%x} to work correctly
# simpler approach: just source it
source "$LIB_CONFIG"

echo "VIBE_ROOT resolved to: $VIBE_ROOT"
echo "Expected: $(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "$VIBE_ROOT" == "$HOME" ]]; then
    echo "FAIL: VIBE_ROOT fallback to HOME triggered."
fi
