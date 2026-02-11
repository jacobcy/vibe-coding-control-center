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

# 2. Verify vibe flow
echo -n "Testing 'vibe flow'... "
if vibe flow 2>&1 | grep -q "vibe flow"; then
    echo "OK"
else
    echo "FAILED (vibe flow command not working)"
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
VIBE_HOME="${VIBE_HOME:-$HOME/.vibe}"
VIBE_KEYS="$VIBE_HOME/keys.env"
mkdir -p "$(dirname "$VIBE_KEYS")"
echo "TEST_KEY=ALIGNED" > "$VIBE_KEYS"

# Check if doctor (formerly status) sees it - it should say "Found"
if vibe doctor | grep -q "Found ($VIBE_HOME/keys.env)"; then
    echo "OK"
else
    echo "FAILED (doctor still looking in wrong path)"
    exit 1
fi

echo "=== All CLI alignment checks passed! ==="
