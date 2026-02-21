#!/usr/bin/env zsh
# tests/test_vibe_chat_intent.sh
# End-to-end tests for vibe chat intent routing

set -e

# Test setup
export VIBE_HOME_OVERRIDE="/tmp/vibe-chat-test-$$"
export VIBE_HOME="$VIBE_HOME_OVERRIDE"

echo "=== Vibe Chat Intent E2E Tests ==="
echo "Test directory: $VIBE_HOME"
echo ""

# Setup
setup() {
    mkdir -p "$VIBE_HOME/keys"
    mkdir -p "$VIBE_HOME/tools"

    # Create test key files
    cat > "$VIBE_HOME/keys/anthropic.env" << 'EOF'
ANTHROPIC_AUTH_TOKEN=test-token
EOF

    cat > "$VIBE_HOME/keys/openai.env" << 'EOF'
OPENAI_API_KEY=test-key
EOF

    ln -sfn "anthropic.env" "$VIBE_HOME/keys/current"

    # Create vibe.yaml
    cat > "$VIBE_HOME/vibe.yaml" << 'EOF'
version: "1.0"
name: "test-env"
keys:
  current: anthropic
mcp:
  - github
EOF
}

# Cleanup
cleanup() {
    rm -rf "$VIBE_HOME"
}

# Test intent routing
test_intent() {
    local intent="$1"
    local message="$2"
    local expected="$3"

    echo "Test: $intent"

    result=$(bin/vibe chat "$message" 2>&1)

    if echo "$result" | grep -qi "$expected"; then
        echo "  ✓ PASS: '$message' -> $intent"
        return 0
    else
        echo "  ✗ FAIL: '$message' did not match expected: $expected"
        echo "  Output: $result"
        return 1
    fi
}

# Run tests
main() {
    local failed=0

    setup

    echo "--- Keys Intents ---"
    test_intent "keys_list" "列出密钥" "Key groups" || ((failed++))
    test_intent "keys_current" "当前密钥" "Current key group" || ((failed++))
    test_intent "keys_use" "切换到 openai" "Switched to key group" || ((failed++))

    echo ""
    echo "--- Tool Intents ---"
    test_intent "tool_list" "列出工具" "Available tools" || ((failed++))
    test_intent "tool_install" "安装 claude" "Installed tool" || ((failed++))

    echo ""
    echo "--- Status Intents ---"
    test_intent "status" "检查状态" "Environment Status" || ((failed++))

    echo ""
    echo "--- MCP Intents ---"
    test_intent "mcp_list" "列出 mcp" "MCP servers" || ((failed++))

    cleanup

    echo ""
    if [[ $failed -eq 0 ]]; then
        echo "=== All intent tests passed! ==="
        return 0
    else
        echo "=== $failed test(s) failed ==="
        return 1
    fi
}

main "$@"
