#!/usr/bin/env zsh
# 测试别名修复脚本

set -e

# 颜色
green='\033[0;32m'
red='\033[0;31m'
nc='\033[0m'

echo "=== 别名修复测试 ==="
echo ""

# 测试 1: 语法检查
echo -n "Test 1: worktree.sh 语法检查... "
if zsh -n ../config/aliases/worktree.sh 2>/dev/null; then
    echo "${green}PASS${nc}"
else
    echo "${red}FAIL${nc}"
    exit 1
fi

echo -n "Test 2: tmux.sh 语法检查... "
if zsh -n ../config/aliases/tmux.sh 2>/dev/null; then
    echo "${green}PASS${nc}"
else
    echo "${red}FAIL${nc}"
    exit 1
fi

# 测试 2: 验证修复内容
echo -n "Test 3: wt 命令使用 git worktree list... "
if grep -q "git worktree list --porcelain" ../config/aliases/worktree.sh; then
    echo "${green}PASS${nc}"
else
    echo "${red}FAIL${nc}"
    exit 1
fi

echo -n "Test 4: vtls 命令 status_icon 变量名... "
if grep -q "status_icon" ../config/aliases/tmux.sh; then
    echo "${green}PASS${nc}"
else
    echo "${red}FAIL${nc}"
    exit 1
fi

# 测试 3: 确保没有使用 status 变量（使用词边界匹配）
echo -n "Test 5: vtls 没有使用 status 保留字... "
# 使用正则表达式匹配 'local status=' 而不是 'local status_icon='
if grep -E '\blocal\s+status\s*=' ../config/aliases/tmux.sh 2>/dev/null | grep -qv 'status_icon'; then
    echo "${red}FAIL${nc} (仍使用 status 变量)"
    exit 1
else
    echo "${green}PASS${nc}"
fi

echo ""
echo "=== 所有测试通过! ==="
