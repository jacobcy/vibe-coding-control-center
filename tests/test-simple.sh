#!/bin/zsh
# Vibe Alias 简单测试

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASSED=0
FAILED=0

PROJECT_ROOT="$(cd "$(dirname $0)/.." && pwd)"

test_file() {
    local file="$1"
    local name=$(basename "$file")
    if zsh -n "$file" 2>/dev/null; then
        echo "✓ $name"
        ((PASSED++))
    else
        echo "✗ $name"
        ((FAILED++))
    fi
}

echo "=== Vibe Alias 测试 ==="
echo ""
echo "语法检查:"

test_file "$PROJECT_ROOT/config/aliases.sh"
test_file "$PROJECT_ROOT/config/aliases/claude.sh"
test_file "$PROJECT_ROOT/config/aliases/opencode.sh"
test_file "$PROJECT_ROOT/config/aliases/openspec.sh"
test_file "$PROJECT_ROOT/config/aliases/vibe.sh"
test_file "$PROJECT_ROOT/config/aliases/git.sh"
test_file "$PROJECT_ROOT/config/aliases/tmux.sh"
test_file "$PROJECT_ROOT/config/aliases/worktree.sh"

echo ""
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ 所有测试通过 ($PASSED)${NC}"
    exit 0
else
    echo -e "${RED}✗ $FAILED 个测试失败${NC}"
    exit 1
fi
