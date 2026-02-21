#!/usr/bin/env zsh
# tests/test_vibe_keys.sh
# End-to-end tests for vibe keys command

set -e

# Test setup
export VIBE_HOME_OVERRIDE="/tmp/vibe-test-$$"
export VIBE_HOME="$VIBE_HOME_OVERRIDE"

echo "=== Vibe Keys E2E Tests ==="
echo "Test directory: $VIBE_HOME"
echo ""

# Setup
setup() {
    mkdir -p "$VIBE_HOME/keys"

    # Create test key files
    cat > "$VIBE_HOME/keys/anthropic.env" << 'EOF'
ANTHROPIC_AUTH_TOKEN=test-token-123
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-5
EOF

    cat > "$VIBE_HOME/keys/openai.env" << 'EOF'
OPENAI_API_KEY=test-openai-key
OPENAI_BASE_URL=https://api.openai.com
EOF

    # Create current symlink
    ln -sfn "anthropic.env" "$VIBE_HOME/keys/current"

    # Create vibe.yaml
    cat > "$VIBE_HOME/vibe.yaml" << 'EOF'
version: "1.0"
name: "test-env"
keys:
  current: anthropic
EOF
}

# Cleanup
cleanup() {
    rm -rf "$VIBE_HOME"
}

# Test 1: List keys
test_list() {
    echo "Test 1: vibe keys list"
    result=$(bin/vibe keys list 2>&1)

    if echo "$result" | grep -q "anthropic"; then
        echo "  ✓ PASS: Found anthropic in list"
    else
        echo "  ✗ FAIL: anthropic not found in list"
        return 1
    fi

    if echo "$result" | grep -q "openai"; then
        echo "  ✓ PASS: Found openai in list"
    else
        echo "  ✗ FAIL: openai not found in list"
        return 1
    fi
}

# Test 2: Current key group
test_current() {
    echo "Test 2: vibe keys current"
    result=$(bin/vibe keys current 2>&1)

    if echo "$result" | grep -q "anthropic"; then
        echo "  ✓ PASS: Current group is anthropic"
    else
        echo "  ✗ FAIL: Current group not anthropic"
        return 1
    fi
}

# Test 3: Switch key group
test_switch() {
    echo "Test 3: vibe keys use openai"
    bin/vibe keys use openai >/dev/null 2>&1

    result=$(bin/vibe keys current 2>&1)
    if echo "$result" | grep -q "openai"; then
        echo "  ✓ PASS: Switched to openai"
    else
        echo "  ✗ FAIL: Failed to switch to openai"
        return 1
    fi

    # Switch back
    bin/vibe keys use anthropic >/dev/null 2>&1
}

# Test 4: Set key
test_set() {
    echo "Test 4: vibe keys set"
    bin/vibe keys set "TEST_KEY=test-value-456" >/dev/null 2>&1

    # Verify key was set
    if grep -q "TEST_KEY=test-value-456" "$VIBE_HOME/keys/anthropic.env"; then
        echo "  ✓ PASS: Key was set"
    else
        echo "  ✗ FAIL: Key was not set"
        return 1
    fi
}

# Test 5: Get key
test_get() {
    echo "Test 5: vibe keys get"
    result=$(bin/vibe keys get ANTHROPIC_MODEL 2>&1)

    if echo "$result" | grep -q "claude-sonnet-4-5"; then
        echo "  ✓ PASS: Got correct key value"
    else
        echo "  ✗ FAIL: Key value incorrect"
        return 1
    fi
}

# Test 6: Create new key group
test_create() {
    echo "Test 6: vibe keys create"
    bin/vibe keys create test-provider >/dev/null 2>&1

    if [[ -f "$VIBE_HOME/keys/test-provider.env" ]]; then
        echo "  ✓ PASS: Created new key group"
    else
        echo "  ✗ FAIL: Failed to create key group"
        return 1
    fi
}

# Run tests
main() {
    local failed=0

    setup

    test_list || ((failed++))
    test_current || ((failed++))
    test_switch || ((failed++))
    test_set || ((failed++))
    test_get || ((failed++))
    test_create || ((failed++))

    cleanup

    echo ""
    if [[ $failed -eq 0 ]]; then
        echo "=== All tests passed! ==="
        return 0
    else
        echo "=== $failed test(s) failed ==="
        return 1
    fi
}

main "$@"
