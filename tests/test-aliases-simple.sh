#!/usr/bin/env zsh
# ======================================================
# Vibe Alias 测试套件 - 简化版
# ======================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 统计
PASSED=0
FAILED=0

# 测试函数
test_syntax() {
    local file="$1"
    local name=$(basename "$file")
    echo -n "Testing syntax: $name ... "
    if zsh -n "$file" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED${NC}"
        ((FAILED++))
    fi
}

# 主程序
echo "=== Vibe Alias 测试 ==="
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 语法检查
echo "1. 语法检查"
test_syntax "$PROJECT_ROOT/config/aliases.sh"
test_syntax "$PROJECT_ROOT/config/aliases/claude.sh"
test_syntax "$PROJECT_ROOT/config/aliases/opencode.sh"
test_syntax "$PROJECT_ROOT/config/aliases/openspec.sh"
test_syntax "$PROJECT_ROOT/config/aliases/vibe.sh"
test_syntax "$PROJECT_ROOT/config/aliases/git.sh"
test_syntax "$PROJECT_ROOT/config/aliases/tmux.sh"
test_syntax "$PROJECT_ROOT/config/aliases/worktree.sh"

# 结果
echo ""
TOTAL=$((PASSED + FAILED))
echo "结果: $PASSED/$TOTAL 通过"

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}✗ 有 $FAILED 个测试失败${NC}"
    exit 1
fi
