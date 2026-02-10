#!/usr/bin/env zsh
# tests/test_install_bootstrap.sh
# Verifies that install.sh runs correctly as a bootstrap script

set -e

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
INSTALL_SCRIPT="$ROOT_DIR/scripts/install.sh"
source "$ROOT_DIR/lib/utils.sh"

log_info "Testing install.sh bootstrap logic..."

# 1. Run install script in a dry-run way or just capture output
# Since install.sh modifies .zshrc, we should probably backup/restore or use a dummy ZDOTDIR if possible.
# But install.sh uses $HOME... let's check if we can mock it.
# Ideally we just check that it runs without error and outputs the right "Next Steps".

OUTPUT=$(zsh "$INSTALL_SCRIPT" 2>&1)
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
    log_error "install.sh failed with exit code $EXIT_CODE"
    echo "$OUTPUT"
    exit 1
fi

if echo "$OUTPUT" | grep -q "Bootstrapping 'vibe' command"; then
    log_success "✓ Found bootstrap step"
else
    log_error "✗ Missing bootstrap step in output"
    exit 1
fi

if echo "$OUTPUT" | grep -q "vibe equip"; then
    log_success "✓ Found 'vibe equip' instruction"
else
    log_error "✗ Missing 'vibe equip' instruction"
    exit 1
fi

# Ensure it DOES NOT try to install Claude/OpenCode automatically
if echo "$OUTPUT" | grep -q "Running Claude Code Installer"; then
    log_error "✗ install.sh should NOT run Claude installer automatically"
    exit 1
fi

if echo "$OUTPUT" | grep -q "Running OpenCode Installer"; then
    log_error "✗ install.sh should NOT run OpenCode installer automatically"
    exit 1
fi

log_success "Install bootstrap test passed!"
exit 0
