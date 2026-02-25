#!/bin/zsh
# Vibe Alias 测试 - 最简版

PASSED=0
FAILED=0

echo "=== Vibe Alias 测试 ==="
echo ""

PROJECT_ROOT="$(cd "$(dirname $0)/.." && pwd)"

for file in \
    "$PROJECT_ROOT/config/aliases.sh" \
    "$PROJECT_ROOT/config/aliases/claude.sh" \
    "$PROJECT_ROOT/config/aliases/opencode.sh" \
    "$PROJECT_ROOT/config/aliases/openspec.sh" \
    "$PROJECT_ROOT/config/aliases/vibe.sh" \
    "$PROJECT_ROOT/config/aliases/git.sh" \
    "$PROJECT_ROOT/config/aliases/tmux.sh" \
    "$PROJECT_ROOT/config/aliases/worktree.sh"
do
    name=$(basename "$file")
    if zsh -n "$file" 2>/dev/null; then
        echo "✓ $name"
        ((PASSED++))
    else
        echo "✗ $name"
        ((FAILED++))
    fi
done

echo ""
echo "结果: $PASSED/$(($PASSED + $FAILED)) 通过"

if [[ $FAILED -eq 0 ]]; then
    echo "✓ 所有测试通过！"
    exit 0
else
    echo "✗ 有 $FAILED 个测试失败"
    exit 1
fi
