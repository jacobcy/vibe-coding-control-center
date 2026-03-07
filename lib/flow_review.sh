#!/usr/bin/env zsh
# lib/flow_review.sh - PR review command handlers for flow module

_flow_review() {
  local target="" pr_info number title state decision mergeable url comments retry=0 ci_status="PENDING" rollup_state="SUCCESS" local_mode=0 json_output=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        _flow_review_usage
        return 0
        ;;
      --local)
        local_mode=1
        shift
        ;;
      --json)
        json_output=1
        shift
        ;;
      *)
        target="$1"
        shift
        ;;
    esac
  done
  vibe_require git || return 1
  [[ -z "$target" ]] && target=$(git branch --show-current)

  if [[ $local_mode -eq 1 ]]; then
    # Try codex first
    if vibe_has codex; then
      log_step "Running local codebase review via Codex..."
      mkdir -p .agent
      if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
        log_info "Uncommitted changes detected. Running: codex review --uncommitted"
        codex review --uncommitted
      else
        log_info "Working directory clean. Running against origin/main..."
        codex review --base main
      fi
      log_success "Local review complete."
      return 0
    fi

    # Fallback to copilot
    if vibe_has copilot; then
      log_step "Codex not found. Falling back to GitHub Copilot..."
      log_info "Note: Copilot review is less comprehensive than Codex."
      mkdir -p .agent
      if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
        log_info "Uncommitted changes detected. Running: copilot review --uncommitted"
        copilot review --uncommitted 2>/dev/null || copilot review
      else
        log_info "Working directory clean. Running against origin/main..."
        copilot review --base main 2>/dev/null || copilot review
      fi
      log_success "Local review complete (via Copilot fallback)."
      return 0
    fi

    # No local LLM available
    log_error "Neither codex nor copilot CLI found. Cannot run local review."
    log_info "Install one of the following:"
    log_info "  - codex: npm install -g @anthropic/codex"
    log_info "  - copilot: Install GitHub Copilot CLI extension"
    return 1
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
