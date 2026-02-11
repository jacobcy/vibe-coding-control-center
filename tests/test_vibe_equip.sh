#!/usr/bin/env zsh
# tests/test_vibe_equip.sh
# Test vibe equip command

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/bin:$PATH"

echo "=== Testing vibe equip command ==="

# Test 1: vibe equip help
echo -n "Test 1: vibe equip --help ... "
if vibe equip --help | grep -q "Install/update AI tools"; then
    echo "✅"
else
    echo "❌ FAILED: Help text not found"
    exit 1
fi

# Test 2: vibe equip exit option
echo -n "Test 2: vibe equip (exit option 3) ... "
# Input '3' to select "Back" which returns/exits.
output=$(printf "3\n\n" | vibe equip 2>&1)

if echo "$output" | grep -q "EQUIPPING TOOLS"; then
    echo "✅"
else
    echo "❌ FAILED: Expected menu output, got:"
    echo "$output"
    exit 1
fi

echo "=== All vibe equip tests passed! ==="
