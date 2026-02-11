#!/usr/bin/env zsh
# tests/test_vibe_chat.sh
# Test vibe chat command

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/bin:$PATH"

# Mock directory
MOCK_DIR="$(mktemp -d)"
export PATH="$MOCK_DIR:$PATH"

# Create mock tools
cat > "$MOCK_DIR/opencode" << 'EOF'
#!/bin/sh
if [ "$1" = "run" ]; then
    echo "MOCK_OPENCODE_RUN: $2"
else
    echo "MOCK_OPENCODE_INTERACTIVE"
fi
EOF
chmod +x "$MOCK_DIR/opencode"

cat > "$MOCK_DIR/claude" << 'EOF'
#!/bin/sh
if [ "$1" = "-p" ]; then
    echo "MOCK_CLAUDE_PROMPT: $2"
else
    echo "MOCK_CLAUDE_INTERACTIVE"
fi
EOF
chmod +x "$MOCK_DIR/claude"

echo "=== Testing vibe chat command ==="

# Test 1: vibe chat (interactive/no args) with opencode default
echo -n "Test 1: vibe chat (interactive) ... "
export VIBE_DEFAULT_TOOL="opencode"
output=$(vibe chat 2>&1)
if echo "$output" | grep -q "MOCK_OPENCODE_INTERACTIVE"; then
    echo "✅"
else
    echo "❌ FAILED: Expected MOCK_OPENCODE_INTERACTIVE, got:"
    echo "$output"
    rm -rf "$MOCK_DIR"
    exit 1
fi

# Test 2: vibe chat "query" with opencode default
echo -n "Test 2: vibe chat 'query' ... "
output=$(vibe chat "how to test" 2>&1)
if echo "$output" | grep -q "MOCK_OPENCODE_RUN: how to test"; then
    echo "✅"
else
    echo "❌ FAILED: Expected MOCK_OPENCODE_RUN, got:"
    echo "$output"
    rm -rf "$MOCK_DIR"
    exit 1
fi

# Test 3: vibe chat with claude default
echo -n "Test 3: vibe chat (claude) ... "
export VIBE_DEFAULT_TOOL="claude"
output=$(vibe chat "how to code" 2>&1)
if echo "$output" | grep -q "MOCK_CLAUDE_PROMPT: how to code"; then
    echo "✅"
else
    echo "❌ FAILED: Expected MOCK_CLAUDE_PROMPT, got:"
    echo "$output"
    rm -rf "$MOCK_DIR"
    exit 1
fi

# Test 4: vibe chat help
echo -n "Test 4: vibe chat help ... "
if vibe chat --help | grep -q "用法:"; then
    echo "✅"
else
    echo "❌ FAILED: Help text not found"
    rm -rf "$MOCK_DIR"
    exit 1
fi

echo "=== All vibe chat tests passed! ==="
rm -rf "$MOCK_DIR"
