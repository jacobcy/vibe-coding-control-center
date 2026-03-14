#!/usr/bin/env zsh
# docs/v3/examples/flow_review.sh
# 示例目标：
# 1. 如何读取远端 PR 现场
# 2. 如何调用本地 agent 生成 review
# 3. 如何把 review 结果回贴到 PR

set -euo pipefail

get_current_pr_json() {
  local target="${1:-$(git branch --show-current)}"
  gh pr view "$target" \
    --json number,title,body,headRefName,baseRefName,reviewDecision,statusCheckRollup
}

build_local_review_prompt() {
  local pr_json="$1"
  local diff_text="$2"

  jq -rn \
    --argjson pr "$pr_json" \
    --arg diff "$diff_text" '
      "Review PR #" + ($pr.number|tostring) + ": " + $pr.title + "\n\n"
      + "Base: " + $pr.baseRefName + "\n"
      + "Head: " + $pr.headRefName + "\n\n"
      + "Body:\n" + ($pr.body // "") + "\n\n"
      + "Diff:\n" + $diff + "\n\n"
      + "请给出结构化代码审查：风险、回归、遗漏测试、建议。"
    '
}

run_local_agent_review() {
  local prompt="$1"
  codex exec --full-auto "$prompt"
}

publish_review_comment() {
  local pr_number="$1"
  local review_body="$2"
  gh pr comment "$pr_number" --body "$review_body"
}

main() {
  local pr_json diff_text prompt review_body pr_number

  pr_json="$(get_current_pr_json "${1:-}")"
  pr_number="$(printf '%s\n' "$pr_json" | jq -r '.number')"
  diff_text="$(git diff --no-ext-diff origin/main...HEAD)"
  prompt="$(build_local_review_prompt "$pr_json" "$diff_text")"
  review_body="$(run_local_agent_review "$prompt")"

  printf '%s\n' "$review_body"
  publish_review_comment "$pr_number" "$review_body"
}

main "$@"

_flow_review_usage() {
  echo "${BOLD}Vibe Flow Review${NC}"
  echo ""
  echo "Usage: ${CYAN}vibe flow review${NC} [options] [<pr-or-branch>|--branch <ref>]"
  echo ""
  echo "审计 PR 的实时真源状态（CI 结果、评审意见、合规性），或执行本地 AI 代码审查。"
  echo ""
  echo "核心职责："
  echo "  1. 状态提取：拉取云端 PR 的评审决策 (Review Decision)"
  echo "  2. 质量审计：实时拉取 CI/Checks 运行状态 (GitHub Actions)"
  echo "  3. 交互查看：显示最近 3 条 review comments"
  echo "  4. 本地审查：使用 --local 调用本地 LLM 进行深度静态分析"
  echo ""
  echo "选项："
  echo "  --local          自动选择本地 LLM（优先 codex，fallback copilot）"
  echo "  --local=codex    强制使用 Codex 本地审查"
  echo "  --local=copilot  强制使用 GitHub Copilot 审查"
  echo "  --json           输出 PR 详细数据与结构化 review evidence（用于程序化调用）"
  echo "  --branch <ref>   指定要查看的分支或 PR 号 (默认: 当前分支)"
  echo ""
  echo "本地 LLM 工具："
  echo "  ${GREEN}codex${NC}    - OpenAI Codex CLI (推荐，专业审查能力)"
  echo "             安装: npm install -g @openai/codex"
  echo "  ${GREEN}copilot${NC}  - GitHub Copilot CLI (通用助手)"
  echo "             安装: 安装 GitHub Copilot CLI 扩展"
  echo ""
  echo "示例："
  echo "  ${CYAN}vibe flow review${NC}              # 查看当前分支的 PR 状态"
  echo "  ${CYAN}vibe flow review 42${NC}           # 查看 PR #42 的状态"
  echo "  ${CYAN}vibe flow review --local${NC}      # 本地审查（自动选择 LLM）"
  echo "  ${CYAN}vibe flow review --local=codex${NC}    # 强制使用 codex"
  echo "  ${CYAN}vibe flow review --json${NC}       # JSON 输出，含 reviewEvidence 摘要"
}
