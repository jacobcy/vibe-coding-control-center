#!/usr/bin/env zsh
# Test: vibe -g (global flag)

set -e

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source test utilities if available
if [[ -f "$SCRIPT_DIR/test_utils.sh" ]]; then
    source "$SCRIPT_DIR/test_utils.sh"
else
    # Minimal test utilities
    test_pass() { echo "✅ PASS: $1"; }
    test_fail() { echo "❌ FAIL: $1"; exit 1; }
fi

echo "=== Testing vibe -g (global flag) ==="
echo ""

# Setup: Create fake local .vibe directory to distinguish from global
mkdir -p "$PROJECT_ROOT/.vibe"
echo "TEST_LOCAL=1" > "$PROJECT_ROOT/.vibe/keys.env"

cleanup() {
    rm -rf "$PROJECT_ROOT/.vibe"
}
trap cleanup EXIT

# Test 1: Check if global installation exists
echo -n "Test 1: Global installation check... "
GLOBAL_VIBE="$HOME/.vibe/bin/vibe"
if [[ -x "$GLOBAL_VIBE" ]]; then
    test_pass "Global vibe found at $GLOBAL_VIBE"
else
    echo "⚠️  SKIP: Global installation not found (expected for branch-only setup)"
    echo "   To enable this test, run: cd main && ./scripts/install.sh"
    exit 0
fi

# Test 2: -g flag shows version (basic execution test)
echo -n "Test 2: vibe -g --version... "
if output=$("$PROJECT_ROOT/bin/vibe" -g --version 2>&1); then
    test_pass "Command executed successfully"
else
    test_fail "Failed to execute vibe -g --version"
fi

# Test 3: -g flag forwards to global (check VIBE_ROOT differs)
echo -n "Test 3: -g forwards to global installation... "

# Debug: Show where we are running from
echo "DEBUG: PROJECT_ROOT=$PROJECT_ROOT" >&2

# Run local status
"$PROJECT_ROOT/bin/vibe" env status > local_status.tmp 2>&1
cat local_status.tmp >&2

# Run global status
"$PROJECT_ROOT/bin/vibe" -g env status > global_status.tmp 2>&1
cat global_status.tmp >&2

# Extract Config Home
local_home=$(grep "Config Home" local_status.tmp | sed 's/Config Home: //')
global_home=$(grep "Config Home" global_status.tmp | sed 's/Config Home: //')

# Cleanup temps
rm -f local_status.tmp global_status.tmp

if [[ -n "$local_home" && -n "$global_home" && "$local_home" != "$global_home" ]]; then
    test_pass "Local and global VIBE_HOME differ (correct forwarding)"
    echo "   Local:  $local_home"
    echo "   Global: $global_home"
else
    # This might be OK if running from global installation
    if [[ "$PROJECT_ROOT" == "$HOME/.vibe" ]]; then
        test_pass "Running from global installation (expected same VIBE_HOME)"
    else
        test_fail "VIBE_HOME should differ between local and global"
        echo "   Local:  '$local_home'"
        echo "   Global: '$global_home'"
    fi
fi

# Test 4: -g with subcommand (env show)
echo -n "Test 4: vibe -g env show... "
if output=$("$PROJECT_ROOT/bin/vibe" -g env show 2>&1); then
    test_pass "Subcommand executed via -g"
else
    test_fail "Failed to execute vibe -g env show"
fi

# Test 5: Arguments are preserved
echo -n "Test 5: vibe -g help env... "
if output=$("$PROJECT_ROOT/bin/vibe" -g help env 2>&1); then
    test_pass "Arguments passed correctly"
else
    test_fail "Failed to pass arguments through -g"
fi

echo ""
# Test 6: -g flag handled in any position (e.g. vibe help -g)
echo -n "Test 6: vibe help -g... "
if output=$("$PROJECT_ROOT/bin/vibe" help -g 2>&1); then
    test_pass "Command 'vibe help -g' executed successfully"
else
    test_fail "Failed to execute 'vibe help -g'"
fi

echo ""
echo "=== All tests passed ==="
