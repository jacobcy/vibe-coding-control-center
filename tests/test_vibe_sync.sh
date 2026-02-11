#!/usr/bin/env zsh
# tests/test_vibe_sync.sh
# Test vibe sync command

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/bin:$PATH"

# Setup test environment
MOCK_DIR="$(mktemp -d)"
cd "$MOCK_DIR"

# Initialize a git repository
git init >/dev/null
git config user.name "Original User"
git config user.email "original@example.com"

echo "=== Testing vibe sync command ==="

# Test 1: vibe sync inside git repo (simulating prompt user choice)
# We need to simulate the prompt_user utility. 
# Since vibe-sync sources lib/utils.sh, we can override the function if we source everything 
# OR we can mock the behavior by feeding input.
# The script uses `read` or similar from `prompt_user`. 
# Let's assume `vibe sync` takes "opencode" as input:

echo -n "Test 1: vibe sync (interactive input: claude) ... "
# The prompt asks for agent (claude/opencode/codex).
# We'll feed "claude" into stdin.
printf "claude\n" | vibe sync > /dev/null

# Check results
name=$(git config user.name)
email=$(git config user.email)

if [[ "$name" == "Agent-Claude" && "$email" == "agent-claude@vibecoding.ai" ]]; then
    echo "✅"
else
    echo "❌ FAILED: Got '$name' <$email>"
    rm -rf "$MOCK_DIR"
    exit 1
fi

# Test 2: Directory pattern detection
# Try to rename directory to wt-opencode-feature
cd ..
mv "$MOCK_DIR" "wt-opencode-feature"
MOCK_DIR_NEW="wt-opencode-feature"
cd "$MOCK_DIR_NEW"

echo -n "Test 2: vibe sync (auto-detect pattern) ... "
# It should detect "opencode" and set default, but still prompt for confirmation.
# We press enter to accept the default.
printf "\n" | vibe sync > /dev/null

name=$(git config user.name)
email=$(git config user.email)

if [[ "$name" == "Agent-Opencode" && "$email" == "agent-opencode@vibecoding.ai" ]]; then
    echo "✅"
else
    echo "❌ FAILED: Got '$name' <$email>"
    cd ..
    rm -rf "$MOCK_DIR_NEW"
    exit 1
fi

echo "=== All vibe sync tests passed! ==="
cd ..
rm -rf "$MOCK_DIR_NEW"
