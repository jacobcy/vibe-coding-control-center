#!/usr/bin/env zsh
# tests/test_cli_alignment.sh

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/bin:$PATH"

echo "=== Testing CLI Alignment ==="

# 1. Verify vibe-doctor
echo -n "Testing 'vibe doctor'... "
if vibe doctor | grep -q "SYSTEM HEALTH STATUS"; then
    echo "OK"
else
    echo "FAILED"
    exit 1
fi

# 2. Verify vibe tdd
echo -n "Testing 'vibe tdd'... "
# We expect a usage error if we don't provide args, but not an "Unknown subcommand" error
if vibe tdd 2>&1 | grep -q "Usage: vibe tdd new"; then
    echo "OK"
else
    echo "FAILED (likely dispatcher didn't find the shim)"
    exit 1
fi

# 3. Verify help output
echo -n "Testing 'vibe help' doctor listing... "
if vibe help | grep -q "doctor"; then
    echo "OK"
else
    echo "FAILED (help not updated)"
    exit 1
fi

# 4. Verify path consistency (Mocking keys.env)
echo -n "Testing key path consistency... "
VIBE_KEYS="$HOME/.vibe/keys.env"
mkdir -p "$(dirname "$VIBE_KEYS")"
echo "TEST_KEY=ALIGNED" > "$VIBE_KEYS"

# Check if doctor (formerly status) sees it - it should say "Found"
if vibe doctor | grep -q "Found (~/.vibe/keys.env)"; then
    echo "OK"
else
    echo "FAILED (doctor still looking in wrong path)"
    exit 1
fi

echo "=== All CLI alignment checks passed! ==="
