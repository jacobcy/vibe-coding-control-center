#!/usr/bin/env zsh
# lib/flow_review.sh - PR review command handlers for flow module

_flow_review() {
  local target="" pr_info number title state decision mergeable url comments retry=0 ci_status="PENDING" rollup_state="SUCCESS" local_mode="" json_output=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        _flow_review_usage
        return 0
        ;;
      --local=*)
        local_mode="${1#*=}"
        [[ -z "$local_mode" ]] && local_mode="auto"
        shift
        ;;
      --local)
        local_mode="auto"
        shift
        ;;
      --json)
        json_output=1
        shift
        ;;
      --branch)
        target="$2"
        shift 2
        ;;
      *)
        target="$1"
        shift
        ;;
    esac
  done
  vibe_require git || return 1
  [[ -z "$target" ]] && target=$(git branch --show-current)

  if [[ -n "$local_mode" ]]; then
    _flow_review_local "$local_mode"
    return $?
  fi

  if ! vibe_has gh; then
    [[ $json_output -eq 1 ]] && echo '{"error": "gh (GitHub CLI) not found"}' && return 1
    log_warn "gh (GitHub CLI) not found. Falling back to local vibe check."
    vibe check
    return 0
  fi

  log_step "Fetching PR status for '$target'..."
  if [[ $json_output -eq 1 ]]; then
    pr_info=$(gh pr view "$target" --json number,title,body,comments,reviews,commits,state,mergedAt,headRefName,baseRefName 2>/dev/null)
    if [[ $? -ne 0 ]]; then
      echo "{\"error\": \"No PR found for '$target'\"}"
      return 1
    fi
    echo "$pr_info"
    return 0
  fi

  pr_info=$(gh pr view "$target" --json number,title,state,reviewDecision,mergeable,url,statusCheckRollup,comments 2>/dev/null)
  [[ $? -ne 0 ]] && { log_warn "No open PR found for '$target'. Running local health check..."; vibe check; return 0; }
  number=$(printf '%s\n' "$pr_info" | jq -r '.number')
  title=$(printf '%s\n' "$pr_info" | jq -r '.title')
  state=$(printf '%s\n' "$pr_info" | jq -r '.state')
  decision=$(printf '%s\n' "$pr_info" | jq -r '.reviewDecision // "PENDING"')
  mergeable=$(printf '%s\n' "$pr_info" | jq -r '.mergeable')
  url=$(printf '%s\n' "$pr_info" | jq -r '.url')
  echo "${BOLD}PR #$number:${NC} $title"
  echo "${CYAN}URL:${NC} $url"
  echo "${CYAN}State:${NC} $state | ${CYAN}Review:${NC} $decision | ${CYAN}Mergeable:${NC} $mergeable"
  log_step "Fetching latest review comments..."
  comments=$(printf '%s\n' "$pr_info" | jq -r '.comments[-3:] | .[]? | "[\(.author.login)]: \(.body)"')
  [[ -n "$comments" ]] && echo "$comments" | sed 's/^/  💬 /' || echo "  (No comments found)"
  while [[ $retry -lt 3 ]]; do
    log_step "Checking CI status (Attempt $((retry + 1))/3)..."
    ci_status=$(gh pr view "$target" --json statusCheckRollup -q '.statusCheckRollup[0].status // "SUCCESS"' 2>/dev/null || echo "SUCCESS")
    rollup_state=$(gh pr view "$target" --json statusCheckRollup -q '.statusCheckRollup[0].state // "SUCCESS"' 2>/dev/null)
    [[ -z "$rollup_state" || "$rollup_state" == "null" ]] && rollup_state="SUCCESS"
    if [[ "$rollup_state" == "PENDING" || "$ci_status" == "in_progress" || "$ci_status" == "queued" ]]; then
      log_info "CI is still running. Waiting 30s..."
      sleep 30
      retry=$((retry + 1))
    else
      PAGER=cat gh pr checks "$target" || true
      break
    fi
  done
  [[ $retry -eq 3 ]] && log_warn "CI is taking too long. Please check manually using: ${CYAN}gh pr checks --watch${NC}"
  if [[ "$decision" == "APPROVED" && "$rollup_state" == "SUCCESS" ]]; then
    log_success "Ready to merge! All criteria met."
  elif [[ "$decision" == "CHANGES_REQUESTED" ]]; then
    log_error "Changes requested. Please address review comments."
  elif [[ "$state" == "MERGED" ]]; then
    log_success "PR already merged. Time to run 'vibe flow done'."
  else
    log_info "PR is currently active. Target: Approval + CI Success."
  fi
}

_flow_review_local() {
  local agent="$1"
  local diff_context=""

  # Prepare diff context
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    log_info "Uncommitted changes detected"
    diff_context="uncommitted"
  else
    log_info "Working directory clean. Comparing against origin/main..."
    diff_context="main"
  fi

  # Determine which agent to use
  case "$agent" in
    codex)
      if ! vibe_has codex; then
        log_error "codex CLI not found. Install: npm install -g @openai/codex"
        return 1
      fi
      log_step "Running local review via Codex..."
      mkdir -p .agent
      if [[ "$diff_context" == "uncommitted" ]]; then
        codex review --uncommitted
      else
        codex review --base main
      fi
      log_success "Codex review complete."
      ;;
    copilot)
      if ! vibe_has copilot; then
        log_error "copilot CLI not found. Install GitHub Copilot CLI extension"
        return 1
      fi
      log_step "Running local review via GitHub Copilot..."
      log_info "Note: Using generic prompt mode (Copilot has no review subcommand)"
      mkdir -p .agent
      local prompt="Review the code changes for quality, bugs, and best practices. "
      prompt+="Focus on: 1) Logic errors, 2) Security issues, 3) Performance, 4) Code style."
      if [[ "$diff_context" == "uncommitted" ]]; then
        prompt+=" Review uncommitted changes."
      else
        prompt+=" Review changes compared to main branch."
      fi
      copilot -p "$prompt" --allow-all-tools
      log_success "Copilot review complete."
      ;;
    auto)
      # Try codex first, then copilot
      if vibe_has codex; then
        _flow_review_local codex
      elif vibe_has copilot; then
        log_info "Codex not found, trying Copilot..."
        _flow_review_local copilot
      else
        log_error "Neither codex nor copilot found."
        log_info "Install one of:"
        log_info "  - codex: npm install -g @openai/codex"
        log_info "  - copilot: Install GitHub Copilot CLI extension"
        return 1
      fi
      ;;
    *)
      log_error "Unknown agent: $agent. Use: codex, copilot, or auto"
      return 1
      ;;
  esac
}

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
  echo "  --json           输出 PR 详细数据的 JSON 格式（用于程序化调用）"
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
  echo "  ${CYAN}vibe flow review --json${NC}       # JSON 输出（用于脚本）"
}
