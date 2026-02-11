#!/usr/bin/env zsh
# tests/test_vibe_env.sh
# Test vibe env command

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/bin:$PATH"

echo "=== Testing vibe env command ==="

# Setup test environment
TEMP_HOME=$(mktemp -d)
export VIBE_HOME="$TEMP_HOME/.vibe"
mkdir -p "$VIBE_HOME"

# Create test keys.env
cat > "$VIBE_HOME/keys.env" << 'EOF'
TEST_KEY="test_value"
ANTHROPIC_AUTH_TOKEN="sk-test-xxx"
VIBE_DEFAULT_TOOL="opencode"
EOF

# Test 1: vibe env get
echo -n "Test 1: vibe env get... "
result=$(vibe env get TEST_KEY 2>&1 | tail -1)
if [[ "$result" == "test_value" ]]; then
    echo "✅"
else
    echo "❌ FAILED: got '$result', expected 'test_value'"
    cat "$VIBE_HOME/keys.env"
    rm -rf "$TEMP_HOME"
    exit 1
fi

# Test 2: vibe env set
echo -n "Test 2: vibe env set... "
vibe env set NEW_KEY "new_value" >/dev/null 2>&1
if grep -q 'NEW_KEY="new_value"' "$VIBE_HOME/keys.env"; then
    echo "✅"
else
    echo "❌ FAILED: NEW_KEY not set"
    rm -rf "$TEMP_HOME"
    exit 1
fi

# Test 3: vibe env show (should work without errors)
echo -n "Test 3: vibe env show... "
if vibe env show >/dev/null 2>&1; then
    echo "✅"
else
    echo "❌ FAILED: vibe env show returned error"
    rm -rf "$TEMP_HOME"
    exit 1
fi

# Test 4: vibe keys (alias) 
echo -n "Test 4: vibe keys alias... "
if vibe keys >/dev/null 2>&1; then
    echo "✅"
else
    echo "❌ FAILED: vibe keys returned error"
    rm -rf "$TEMP_HOME"
    exit 1
fi

# Test 5: vibe env help
echo -n "Test 5: vibe env help... "
if vibe env help | grep -q "Environment variable"; then
    echo "✅"
else
    echo "❌ FAILED: help doesn't contain expected text"
    rm -rf "$TEMP_HOME"
    exit 1
fi

# Cleanup
rm -rf "$TEMP_HOME"

echo "=== All vibe env tests passed! ==="
