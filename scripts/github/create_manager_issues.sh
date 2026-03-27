#!/usr/bin/env zsh
# scripts/github/create_manager_issues.sh
# 创建 vibe-manager 流程优化相关 GitHub Issues
# Usage: zsh scripts/github/create_manager_issues.sh [--dry-run]

set -e

REPO="jacobcy/vibe-coding-control-center"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --help) echo "Usage: zsh scripts/github/create_manager_issues.sh [--dry-run]"; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# 获取 GitHub token
GH_TOKEN=$(gh auth token 2>/dev/null) || { echo "ERROR: gh auth token failed"; exit 1; }

create_issue() {
  local title="$1"
  local body="$2"
  local label="${3:-improvement}"

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run] Would create issue: $title"
    return 0
  fi

  local payload
  payload=$(python3 -c "
import json, sys
print(json.dumps({'title': sys.argv[1], 'body': sys.argv[2], 'labels': sys.argv[3].split(',')}))
" "$title" "$body" "$label")

  local resp
  resp=$(curl -s -X POST \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/$REPO/issues" \
    -d "$payload")

  local num url
  num=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('number','ERROR'))")
  url=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('html_url',''))")

  if [[ "$num" == "ERROR" ]] || [[ -z "$num" ]]; then
    echo "FAILED: $title"
    echo "$resp" | python3 -m json.tool 2>/dev/null | head -20
    return 1
  fi
  echo "Created #$num: $title"
  echo "  $url"
}

# -------------------------------------------------------
# Issue 1: SKILL.md Phase 0 缺失
# -------------------------------------------------------
BODY_PHASE0="## 问题

\`skills/vibe-manager/SKILL.md\` 描述的工作主链从「确认 flow/task/spec」开始，
但没有给出可执行的具体步骤，导致 agent 在 task not bound 的情况下直接开始派发 agent。

## 当前缺陷

SKILL.md 只有抽象目标「确认正确的 flow、task、spec」，未说明：
- 用什么命令检查
- 检查不通过时应该做什么
- task not bound 时必须先执行 \`vibe3 flow bind <issue> --role task\`

## 实际后果

session 中 manager 在 \`task: not bound\` 状态下直接派发 agent，导致流程无效。

## 建议修复

在 SKILL.md Phase 0 增加具体步骤：

\`\`\`bash
vibe3 flow show       # 确认 flow 状态
vibe3 task show       # 确认 task 状态
# 若 task not bound：
vibe3 flow bind <issue-number> --role task
\`\`\`

明确规则：前置检查未通过，manager 不得进入派发阶段。"

create_issue \
  "improvement: vibe-manager SKILL.md 缺少 Phase 0 task binding 前置检查" \
  "$BODY_PHASE0" \
  "improvement"

# -------------------------------------------------------
# Issue 2: SKILL.md 缺少 agent 派发协议和观察循环
# -------------------------------------------------------
BODY_DISPATCH="## 问题

\`skills/vibe-manager/SKILL.md\` 的「选择执行入口」章节只说了「写 prompt 或直接用现有 skill」，
但没有说明如何具体执行，也没有定义派发后的观察行为。

## 缺失内容

**派发协议缺失**：当前 SKILL.md 没有列出这些命令：

\`\`\`bash
vibe3 run --skill <name> --async   # 派发 skill agent
vibe3 run \"instructions\" --async   # 派发 lightweight agent
vibe3 run --plan <file> --async    # 派发 plan agent
\`\`\`

**观察循环缺失**：没有说明：
- 多久查一次状态
- 看哪些字段（run_started / run_done / run_aborted）
- manager 在 agent 运行期间可以做什么（发 issue），不能做什么（写代码）

## 实际后果

manager 派发 async agent 后直接去写代码，打破了职责边界。

## 建议修复

在 SKILL.md 新增「派发协议」和「观察循环」两节，含具体命令示例和行为规则。"

create_issue \
  "improvement: vibe-manager SKILL.md 缺少 agent 派发协议和观察循环描述" \
  "$BODY_DISPATCH" \
  "improvement"

echo "Done."

