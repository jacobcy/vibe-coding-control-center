#!/bin/zsh
# Vibe Alias 测试套件
# 用法: zsh test-final.sh

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

PROJECT_ROOT="$(cd "$(dirname $0)/.." && pwd)"

test_syntax() {
    local file="$1"
    local name=$(basename "$file")
    if zsh -n "$file" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASSED++))
    else
        echo -e "  ${RED}✗${NC} $name"
        ((FAILED++))
    fi
}

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║         Vibe Alias 测试套件                           ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

echo "📋 语法检查:"

test_syntax "$PROJECT_ROOT/config/aliases.sh"
test_syntax "$PROJECT_ROOT/config/aliases/claude.sh"
test_syntax "$PROJECT_ROOT/config/aliases/opencode.sh"
test_syntax "$PROJECT_ROOT/config/aliases/openspec.sh"
test_syntax "$PROJECT_ROOT/config/aliases/vibe.sh"
test_syntax "$PROJECT_ROOT/config/aliases/git.sh"
test_syntax "$PROJECT_ROOT/config/aliases/tmux.sh"
test_syntax "$PROJECT_ROOT/config/aliases/worktree.sh"

echo ""
echo "📊 测试结果:"
echo "  通过: $PASSED"
echo "  失败: $FAILED"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}✗ 有 $FAILED 个测试失败${NC}"
    echo ""
    exit 1
fi
