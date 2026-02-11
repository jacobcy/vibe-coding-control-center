#!/usr/bin/env zsh
# tests/test_vibe_config.sh
# Test vibe config command

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/bin:$PATH"

echo "=== Testing vibe config command ==="

# Setup mock OpenCode config
mkdir -p "$HOME/.config/opencode"
cat > "$HOME/.config/opencode/opencode.json" << 'EOF'
{
  "providers": [
    {"name": "kimi", "apiType": "openai"},
    {"name": "deepseek", "apiType": "openai"}
  ]
}
EOF

# Setup mock Codex config
mkdir -p "$HOME/.codex"
cat > "$HOME/.codex/config.toml" << 'EOF'
model = "gpt-4"
temperature = 0.7
EOF

# Test 1: vibe config (no args - show status)
echo -n "Test 1: vibe config status... "
output=$(vibe config 2>/dev/null)
if echo "$output" | grep -q "AI Tool Configuration Status"; then
    echo "✅"
else
    echo "❌ FAILED: status output missing"
    exit 1
fi

# Test 2: vibe config opencode show
echo -n "Test 2: vibe config opencode show... "
output=$(vibe config opencode show 2>/dev/null)
if echo "$output" | grep -q "kimi"; then
    echo "✅"
else
    echo "❌ FAILED: OpenCode config not shown"
    exit 1
fi



# Test  4: vibe config codex show
echo -n "Test 4: vibe config codex show... "
output=$(vibe config codex show 2>/dev/null)
if echo "$output" | grep -q "gpt-4"; then
    echo "✅"
else
    echo "❌ FAILED: Codex config not shown"
    exit 1
fi

# Test 5: vibe config codex model (get)
echo -n "Test 5: vibe config codex model get... "
model=$(vibe config codex model 2>&1 | grep -v "^✓" | grep -v "^$" | tail -1)
if [[ "$model" == "gpt-4" ]]; then
    echo "✅"
else
    echo "❌ FAILED: got '$model', expected 'gpt-4'"
    exit 1
fi

# Test 6: vibe config codex model (set)
echo -n "Test 6: vibe config codex model set... "
vibe config codex model "deepseek-chat" >/dev/null 2>&1
new_model=$(vibe config codex model 2>&1 | grep -v "^✓" | grep -v "^$" | tail -1)
if [[ "$new_model" == "deepseek-chat" ]]; then
    echo "✅"
else
    echo "❌ FAILED: model not set, got '$new_model'"
    exit 1
fi

# Test 7: vibe config help
echo -n "Test 7: vibe config help... "
if vibe config help | grep -q "AI tool configuration"; then
    echo "✅"
else
    echo "❌ FAILED: help doesn't contain expected text"
    exit 1
fi

echo "=== All vibe config tests passed! ==="
