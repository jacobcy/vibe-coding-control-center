#!/bin/bash
# Sync repository labels to project standards
# Idempotent: creates missing labels, updates existing labels' description/color
# Non-destructive: never deletes labels

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Label Sync Script ===${NC}"
echo "Ensuring all standard labels exist with correct descriptions and colors"
echo "Mode: Idempotent, non-destructive (no deletion)"
echo ""

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: gh CLI not found${NC}"
    echo "Please install GitHub CLI: https://cli.github.com/"
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq not found${NC}"
    echo "Please install jq: https://stedolan.github.io/jq/"
    exit 1
fi

echo -e "${GREEN}✓ Pre-flight checks passed${NC}"
echo ""

# Track sync failures
FAILURES=0

# Function to create or update label (idempotent)
sync_label() {
    local name="$1"
    local description="$2"
    local color="$3"

    # Try to create label, if exists, update it (--force)
    if gh label create "$name" --description "$description" --color "$color" --force 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $name"
    else
        echo -e "${RED}✗${NC} $name (FAILED)"
        FAILURES=$((FAILURES + 1))
    fi
}

echo -e "${BLUE}=== Type Labels ===${NC}"
sync_label "type/feature" "新功能开发" "0075CA"
sync_label "type/fix" "Bug 修复" "D73A4A"
sync_label "type/refactor" "代码重构" "E99695"
sync_label "type/docs" "文档更新" "0075CA"
sync_label "type/test" "测试相关" "FBCA04"
sync_label "type/chore" "杂项改动" "C2E0C6"
sync_label "type/task" "综合性任务（包含多种类型改动）" "D4C5F9"
sync_label "type/perf" "性能优化" "FF9900"

echo ""
echo -e "${BLUE}=== Priority Labels (Numeric) ===${NC}"
sync_label "priority/0" "默认优先级（无标签时）" "DDDDDD"
sync_label "priority/1" "最低优先级改进（nice-to-have）" "C2E0C6"
sync_label "priority/2" "低优先级改进（nice-to-have）" "BFD4B8"
sync_label "priority/3" "一般功能、改进项（等同于 priority/low）" "9FD4AD"
sync_label "priority/4" "一般功能、改进项" "7ED196"
sync_label "priority/5" "重要但非紧急的功能（等同于 priority/medium）" "E3F286"
sync_label "priority/6" "重要但非紧急的功能" "F2E786"
sync_label "priority/7" "核心功能、关键 bug 修复（等同于 priority/high）" "F2B686"
sync_label "priority/8" "极高优先级、重要功能阻断" "F29986"
sync_label "priority/9" "紧急阻断性问题、系统崩溃（等同于 priority/critical）" "D73A4A"

echo ""
echo -e "${BLUE}=== Priority Labels (Legacy) ===${NC}"
sync_label "priority/critical" "紧急阻断性问题（等同于 priority/9）" "D73A4A"
sync_label "priority/high" "高优先级（等同于 priority/7）" "F2B686"
sync_label "priority/medium" "中等优先级（等同于 priority/5）" "E3F286"
sync_label "priority/low" "低优先级（等同于 priority/3）" "9FD4AD"

echo ""
echo -e "${BLUE}=== Roadmap Labels ===${NC}"
sync_label "roadmap/p0" "当前迭代必须完成" "FF0000"
sync_label "roadmap/p1" "下个迭代优先完成" "FF6600"
sync_label "roadmap/p2" "有容量时完成" "FFCC00"
sync_label "roadmap/next" "下个迭代规划中" "99CCFF"
sync_label "roadmap/future" "未来考虑" "CCCCFF"
sync_label "roadmap/rfc" "RFC/设计阶段" "CC99FF"

echo ""
echo -e "${BLUE}=== Scope Labels ===${NC}"
sync_label "scope/python" "Python 代码改动" "0075CA"
sync_label "scope/shell" "Shell 层改动" "E99695"
sync_label "scope/documentation" "文档改动" "0075CA"
sync_label "scope/infrastructure" "基础设施改动" "D4C5F9"
sync_label "scope/skill" "Skill 层改动" "FBCA04"
sync_label "scope/supervisor" "Supervisor 层改动" "9933FF"

echo ""
echo -e "${BLUE}=== Component Labels ===${NC}"
sync_label "component/cli" "CLI 入口" "0075CA"
sync_label "component/client" "Client 封装" "E99695"
sync_label "component/config" "配置管理" "FBCA04"
sync_label "component/flow" "Flow 管理" "C2E0C6"
sync_label "component/logger" "Logger 模块" "D4C5F9"
sync_label "component/orchestra" "Orchestra 谘度和自动化" "FF9933"
sync_label "component/pr" "PR 管理" "7057FF"
sync_label "component/task" "Task 管理" "5319E7"

echo ""
echo -e "${BLUE}=== State Labels (Orchestration) ===${NC}"
sync_label "state/ready" "Ready for manager dispatch" "EEEEEE"
sync_label "state/claimed" "已认领，待进入执行" "BFDADC"
sync_label "state/in-progress" "执行中" "0052CC"
sync_label "state/blocked" "阻塞中" "D73A4A"
sync_label "state/handoff" "待交接" "FBCA04"
sync_label "state/review" "待 review" "5319E7"
sync_label "state/merge-ready" "已满足合并条件" "0E8A16"
sync_label "state/done" "已完成" "0E8A16"
sync_label "state/failed" "Execution failed and needs recovery" "B60205"

echo ""
echo -e "${BLUE}=== Trigger Labels ===${NC}"
sync_label "trigger/ai-review" "触发 AI PR 审查流程（一次性触发器）" "FF9933"

echo ""
echo -e "${BLUE}=== Special Purpose Labels ===${NC}"
sync_label "supervisor" "Supervisor-governed orchestration issue" "9933FF"
sync_label "orchestra" "Orchestra scheduling and automation" "FF9933"
sync_label "tech-debt" "Technical debt tracking" "CC6666"
sync_label "improvement" "Non-urgent improvements and enhancements" "66CC99"
sync_label "breaking-change" "破坏性变更" "B60205"

echo ""
echo -e "${BLUE}=== Mirror Labels ===${NC}"
sync_label "vibe-task" "Track issues intended for vibe roadmap/task intake" "5319E7"

echo ""
echo -e "${BLUE}=== GitHub Default Labels (Keep if exists) ===${NC}"
# These are GitHub default labels, we don't create them but check if they exist
for label in "bug" "documentation" "enhancement" "question"; do
    if gh label list --json name | jq -e ".[] | select(.name == \"$label\")" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $label (GitHub default, preserved)"
    else
        echo -e "${BLUE}○${NC} $label (not present, skipped)"
    fi
done

echo ""
echo -e "${GREEN}=== Label Sync Complete ===${NC}"
echo ""
echo "Summary:"
echo "  - All standard labels synced (created or updated)"
echo "  - Existing labels preserved (no deletion)"
echo "  - GitHub default labels preserved if present"
echo ""
echo "Total labels in repo:"
gh label list --limit 100 --json name | jq 'length'
echo ""

# Report failures and exit with appropriate code
if [ $FAILURES -gt 0 ]; then
    echo -e "${RED}✗ Failed to sync $FAILURES label(s)${NC}"
    exit 1
else
    echo -e "${GREEN}✓ All labels synced successfully${NC}"
fi