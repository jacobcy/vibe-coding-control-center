#!/usr/bin/env zsh
# ======================================================
# Vibe Alias 快速测试脚本
# ======================================================
# 简化版测试，专注于核心功能验证

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
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

test_alias_def() {
    local file="$1"
    local pattern="$2"
    local name="$3"
    echo -n "Testing definition: $name ... "
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED${NC}"
        ((FAILED++))
    fi
}

test_command() {
    local cmd="$1"
    local name="$2"
    echo -n "Testing command: $name ... "
    if eval "$cmd" >/dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAILED${NC}"
        ((FAILED++))
    fi
}

# 主程序
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║       Vibe Alias 快速测试 (Quick Test Suite)         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Project: $PROJECT_ROOT"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. 语法检查
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ${BOLD}1. 语法检查 (Syntax Check)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_syntax "$PROJECT_ROOT/config/aliases.sh"
test_syntax "$PROJECT_ROOT/config/aliases/claude.sh"
test_syntax "$PROJECT_ROOT/config/aliases/opencode.sh"
test_syntax "$PROJECT_ROOT/config/aliases/openspec.sh"
test_syntax "$PROJECT_ROOT/config/aliases/vibe.sh"
test_syntax "$PROJECT_ROOT/config/aliases/git.sh"
test_syntax "$PROJECT_ROOT/config/aliases/tmux.sh"
test_syntax "$PROJECT_ROOT/config/aliases/worktree.sh"

# 2. Alias 定义检查
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ${BOLD}2. Alias 定义检查 (Definition Check)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_alias_def "$PROJECT_ROOT/config/aliases/claude.sh" "alias ccy=" "ccy (Claude continue)"
test_alias_def "$PROJECT_ROOT/config/aliases/claude.sh" "alias ccp=" "ccp (Claude plan mode)"
test_alias_def "$PROJECT_ROOT/config/aliases/vibe.sh" "alias lg='lazygit'" "lg (lazygit)"
test_alias_def "$PROJECT_ROOT/config/aliases/vibe.sh" "alias vc=" "vc (vibe chat)"
test_alias_def "$PROJECT_ROOT/config/aliases/opencode.sh" "alias oo=" "oo (opencode)"
test_alias_def "$PROJECT_ROOT/config/aliases/openspec.sh" "alias os=" "os (openspec)"

# 3. 依赖检查
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ${BOLD}3. 依赖检查 (Dependency Check)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_command "command -v git" "git (required)"
test_command "command -v zsh" "zsh (required)"
test_command "command -v tmux" "tmux (optional)"
test_command "command -v lazygit" "lazygit (optional)"

# 结果汇总
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ${BOLD}测试结果 (Test Results)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

TOTAL=$((PASSED + FAILED))

if [[ $FAILED -eq 0 ]]; then
    echo -e "  总测试数: $TOTAL"
    echo -e "  通过: ${GREEN}$PASSED${NC}"
    echo -e "  失败: $FAILED"
    echo ""
    echo -e "  ${GREEN}✓ 所有测试通过！${NC}"
    echo ""
    exit 0
else
    echo -e "  总测试数: $TOTAL"
    echo -e "  通过: $PASSED"
    echo -e "  失败: ${RED}$FAILED${NC}"
    echo ""
    echo -e "  ${RED}✗ 有 $FAILED 个测试失败${NC}"
    echo ""
    exit 1
fi
