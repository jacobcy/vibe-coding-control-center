#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIBE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_VIBE="$VIBE_ROOT/bin/vibe"

# Helper to look for a key in output
assert_contains() {
    local output="$1"
    local expected="$2"
    if [[ "$output" != *"$expected"* ]]; then
        echo "FAIL: Expected output to contain '$expected', but got:"
        echo "$output"
        return 1
    fi
}

echo "=== Testing Config Isolation ==="

# 1. Setup temp directories
TEST_DIR=$(mktemp -d)
PROJECT_DIR="$TEST_DIR/project"
mkdir -p "$PROJECT_DIR/.vibe"

GLOBAL_DIR="$TEST_DIR/global"
mkdir -p "$GLOBAL_DIR/.vibe"

# 2. Create mock keys.env files
echo "TEST_KEY=local_val" > "$PROJECT_DIR/.vibe/keys.env"
echo "TEST_KEY=global_val" > "$GLOBAL_DIR/.vibe/keys.env"

# 3. Test Global Config (Simulation)
# We mock HOME to point to GLOBAL_DIR
export HOME="$GLOBAL_DIR"

echo "--- Test 1: Global config fallback ---"
cd "$GLOBAL_DIR"
# Run env get. Should return global_val
OUTPUT=$(VIBE_HOME="" "$BIN_VIBE" env get TEST_KEY)
assert_contains "$OUTPUT" "global_val"
echo "PASS: Global config used when in home."

echo "--- Test 2: Local config priority ---"
cd "$PROJECT_DIR"
# Run env get. Should return local_val
OUTPUT=$(VIBE_HOME="" "$BIN_VIBE" env get TEST_KEY)
assert_contains "$OUTPUT" "local_val"
echo "PASS: Local config used when in project directory."

echo "--- Test 3: VIBE_HOME override ---"
# Explicitly set VIBE_HOME to global, even when in project dir
OUTPUT=$(VIBE_HOME="$GLOBAL_DIR/.vibe" "$BIN_VIBE" env get TEST_KEY)
assert_contains "$OUTPUT" "global_val"
echo "PASS: VIBE_HOME override respected."

# Cleanup
rm -rf "$TEST_DIR"
echo "=== All Tests Passed ==="
