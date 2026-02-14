#!/usr/bin/env zsh
# tests/test_cli_alignment.sh

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/bin:$PATH"

echo "=== Testing CLI Alignment ==="

# 1. Verify vibe-check
echo -n "Testing 'vibe check'... "
if vibe check | grep -q "SYSTEM HEALTH STATUS"; then
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
echo -n "Testing 'vibe help' check listing... "
if vibe help | grep -q "check"; then
    echo "OK"
else
    echo "FAILED (help not updated)"
    exit 1
fi

echo "=== All CLI alignment checks passed! ==="
