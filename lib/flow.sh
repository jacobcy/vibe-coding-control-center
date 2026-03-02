#!/usr/bin/env zsh
# lib/flow.sh – Development workflow lifecycle
# Wraps: git worktree, gh pr, lazygit, tmux
# Subcommands: start, review, pr, done, status

[[ -z "${VIBE_ROOT:-}" ]] && { echo "error: VIBE_ROOT not set"; return 1; }

# Detect feature/agent from worktree dir (wt-<agent>-<feature>)
_detect_feature() {
  local dir; dir=$(basename "$PWD")
  [[ "$dir" =~ ^wt-[^-]+-(.+)$ ]] && { echo "${match[1]}"; return 0; }
  return 1
}
_detect_agent() {
  local dir; dir=$(basename "$PWD")
  [[ "$dir" =~ ^wt-([^-]+)- ]] && { echo "${match[1]}"; return 0; }
  echo "claude"
}

_flow_start() {
  local feature="$1" agent="${2:-claude}" base="${3:-main}"
  for arg in "$@"; do
    case "$arg" in --agent=*) agent="${arg#*=}" ;; --base=*) base="${arg#*=}" ;; esac
  done
  [[ -z "$feature" ]] && { log_error "Usage: vibe flow start <feature> [--agent=claude] [--base=main]"; return 1; }

  local wt_dir="wt-${agent}-${feature}" branch="${agent}/${feature}"
  log_step "Creating worktree ${CYAN}${wt_dir}${NC} from ${base}"

  if typeset -f wtnew &>/dev/null; then
    wtnew "$feature" "$agent" "$base" || { log_error "wtnew failed"; return 1; }
  else
    git fetch origin "$base" --quiet 2>/dev/null || true
    git worktree add -b "$branch" "../$wt_dir" "$base" \
      || { log_error "git worktree add failed"; return 1; }
    cd "../$wt_dir" || return 1
  fi

  git config user.name "Agent-${(C)agent}" 2>/dev/null
  mkdir -p docs/prds
  if [[ ! -f "docs/prds/${feature}.md" ]]; then
    printf "# PRD: %s\n## 背景\n_TODO: 描述为什么需要这个功能_\n## 目标\n_TODO: 描述功能目标_\n## 需求清单\n- [ ] 需求1\n- [ ] 需求2\n" "${feature}" > "docs/prds/${feature}.md"
    log_info "Created PRD stub: docs/prds/${feature}.md"
  fi

  # Optional tmux workspace
  if typeset -f vup &>/dev/null && [[ -n "${TMUX:-}" ]]; then
    vup "$wt_dir" "$agent" 2>/dev/null && log_info "tmux workspace created"
  fi

  # Execute project-level post-start hook if available
  if [[ -x "bin/setup" ]]; then
    log_step "Executing project setup hook: bin/setup"
    ./bin/setup || log_warn "Setup hook 'bin/setup' failed"
  elif [[ -x "install.sh" ]]; then
    log_step "Executing project setup hook: install.sh"
    ./install.sh || log_warn "Setup hook 'install.sh' failed"
  fi

  echo ""
  log_success "Feature started: ${BOLD}${feature}${NC}"
  echo "  Directory : ${CYAN}$PWD${NC}"
  echo "  Branch    : ${CYAN}${branch}${NC}"
  echo ""
  echo "${BOLD}Onboarding:${NC} ✅ 工作区已就绪"
  echo "  为保证不产生垃圾代码，请在 AI 助手中输入: ${CYAN}/vibe-new ${feature}${NC}"
  echo "  然后按 Vibe Guard 流程推进开发，完成后执行: ${CYAN}vibe flow review${NC}"
}

_flow_review() {
  local feature="${1:-$(_detect_feature || true)}"
  [[ -z "$feature" ]] && { log_error "Not in a worktree. Specify: vibe flow review <feature>"; return 1; }

  echo "\n${BOLD}${YELLOW}Pre-PR Checklist: ${feature}${NC}"
  echo "  [ ] Tests pass            [ ] Error handling appropriate"
  echo "  [ ] No debug artefacts    [ ] Documentation updated"
  echo "  [ ] LOC ceiling (≤200/file)  [ ] No sensitive data"
  echo ""
  local stats; stats=$(git diff --stat HEAD 2>/dev/null)
  [[ -n "$stats" ]] && { echo "${BOLD}Uncommitted changes:${NC}"; echo "$stats"; echo ""; }

  if vibe_has lazygit; then
    confirm_action "Open lazygit for code review?" && lazygit
  else
    log_info "Tip: install lazygit for interactive review"
    git status --short
  fi
  echo "\n  Next → ${CYAN}vibe flow pr${NC}"
}

_flow_pr() {
  local feature="${1:-$(_detect_feature || true)}"
  [[ -z "$feature" ]] && { log_error "Not in a worktree"; return 1; }
  vibe_has gh || { log_error "GitHub CLI (gh) required — brew install gh"; return 1; }

  local title="feat(${feature}): summary"
  local body="## Changes\n$(git log --oneline main..HEAD 2>/dev/null | sed 's/^/- /')\n\n## Checklist\n- [ ] Tests pass\n- [ ] Docs updated\n- [ ] Code reviewed"

  mkdir -p temp
  echo "$body" > "temp/pr-${feature}.md"
  log_info "PR description → temp/pr-${feature}.md"
  echo ""
  if confirm_action "Create PR '${title}' now?"; then
    if gh pr create --title "$title" --body-file "temp/pr-${feature}.md"; then
      log_success "PR created!"
      echo ""
      echo "${BOLD}Task Completion Reminder:${NC} ⚠️ 不要忘记在 AI 助手中收口该任务！"
      echo "  👉 记得将对应的任务状态更新为 ${CYAN}completed${NC}，并在 registry 大盘中同步。"
    else
      log_error "PR creation failed"
    fi
  fi
  echo "\n  After merge → ${CYAN}vibe flow done${NC}"
}

_flow_done() {
  local feature="${1:-$(_detect_feature || true)}"
  [[ -z "$feature" ]] && { log_error "Not in a worktree"; return 1; }
  local wt_dir; wt_dir=$(basename "$PWD")

  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    log_warn "Uncommitted changes detected"
    confirm_action "Discard and remove worktree anyway?" || { log_info "Aborted."; return 1; }
  fi

  local main_dir
  main_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
  main_dir="${main_dir%/.git}"
  cd "$main_dir" || { log_error "Cannot navigate to main repo"; return 1; }

  log_step "Removing worktree ${CYAN}${wt_dir}${NC}"
  git worktree remove "$wt_dir" --force 2>/dev/null \
    || git worktree remove "../$wt_dir" --force 2>/dev/null \
    || { log_error "Failed to remove worktree"; return 1; }
  log_success "Worktree ${wt_dir} removed — now in: ${CYAN}$PWD${NC}"
  echo ""
  echo "${BOLD}Note:${NC} 若该 worktree 相关的任务还没有在大盘中结算为 completed / archived，请记得收尾清理。"
}

_flow_sync() {
  local current_branch
  local has_fail=0
  current_branch=$(git branch --show-current 2>/dev/null)
  [[ -z "$current_branch" ]] && { log_error "Not in a git repository"; return 1; }
  
  log_step "Syncing from source branch: ${CYAN}$current_branch${NC}"
  
  while read -r wt_path; do
    local wt_branch
    wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)
    
    [[ "$wt_branch" == "$current_branch" ]] && continue
    
    local behind
    behind=$(git rev-list --count "$wt_branch".."$current_branch" 2>/dev/null || echo "0")
    
    if [[ "$behind" -gt 0 ]]; then
      echo "  -> ${CYAN}$wt_branch${NC} is behind by $behind commits. Merging..."
      if git -C "$wt_path" merge "$current_branch" --no-edit >/dev/null 2>&1; then
        log_success "  -> Synced $wt_branch"
      else
        log_error "  -> Merge failed for $wt_branch. Manual resolution required in $wt_path"
        has_fail=1
      fi
    fi
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')

  if [[ "$has_fail" -eq 1 ]]; then
    log_error "Sync completed with failures."
    return 1
  fi
  log_success "Sync complete."
}

_flow_status() {
  local feature="${1:-$(_detect_feature || true)}"
  [[ -z "$feature" ]] && { log_error "Not in a worktree"; return 1; }

  echo "\n${BOLD}${YELLOW}Workflow Status: ${feature}${NC}"
  echo "  Agent     : Agent-${(C)$(_detect_agent)}"
  echo "  Branch    : ${CYAN}$(git branch --show-current 2>/dev/null)${NC}"
  echo "  Directory : ${CYAN}${PWD}${NC}"

  local commits; commits=$(git log --oneline -5 2>/dev/null)
  [[ -n "$commits" ]] && { echo "\n${BOLD}Recent commits:${NC}"; echo "$commits" | sed 's/^/  /'; }

  local changed; changed=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  echo "\n  Uncommitted: ${changed}"
  [[ -f "docs/prds/${feature}.md" ]] && echo "  PRD  : ✅" || echo "  PRD  : ⬜"
  [[ -f "docs/specs/${feature}-spec.md" ]] && echo "  Spec : ✅" || echo "  Spec : ⬜"
  echo ""
}

# ─── Dispatcher ─────────────────────────────────────────
vibe_flow() {
  local cmd="${1:-help}"; shift 1 2>/dev/null || true
  case "$cmd" in
    start)  _flow_start "$@" ;;
    review) _flow_review "$@" ;;
    pr)     _flow_pr "$@" ;;
    done)   _flow_done "$@" ;;
    status) _flow_status "$@" ;;
    sync)   _flow_sync "$@" ;;
    *)
      printf "Usage: vibe flow <command>\n  start  <feature> [--agent=claude] [--base=main]  创建 worktree\n  review [feature]   Pre-PR 检查清单 + lazygit\n  pr     [feature]   生成 PR 并通过 gh 创建\n  done   [feature]   清理 worktree\n  status [feature]   查看 feature 状态\n  sync               同步当前分支的变更到其他所有 worktree 分支\n"
      ;;
  esac
}
