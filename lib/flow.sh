#!/usr/bin/env zsh
[[ -z "${VIBE_ROOT:-}" ]] && { echo "error: VIBE_ROOT not set"; return 1; }

_detect_feature() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-[^-]+-(.+)$ ]] && { echo "${match[1]}"; return 0; }; return 1; }
_detect_agent() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-([^-]+)- ]] && { echo "${match[1]}"; return 0; }; echo "claude"; }
_flow_registry_file() { echo "$(git rev-parse --git-common-dir)/vibe/registry.json"; }
_flow_task_title() { jq -r --arg task_id "$1" '.tasks[]? | select(.task_id == $task_id) | .title // empty' "$2"; }
_flow_set_identity() { git config user.name "$1" 2>/dev/null || git config user.name "$1" || return 1; git config user.email "$1@vibe.coding" 2>/dev/null || git config user.email "$1@vibe.coding"; }
_flow_start_usage() { echo "Usage: vibe flow start <feature> | --task <task-id> [--agent=claude] [--base=main]"; }
_flow_default_agent() { _detect_agent 2>/dev/null || echo "${VIBE_AGENT:-claude}"; }
_flow_require_clean_worktree() { [[ -z "$(git status --porcelain 2>/dev/null)" ]] || { log_error "Refusing to start task from dirty worktree"; return 1; }; }
_flow_require_base_ref() { git fetch origin "$1" --quiet 2>/dev/null || true; git show-ref --verify --quiet "refs/remotes/origin/$1" || { log_error "origin/$1 not found"; return 1; }; }
_flow_branch_exists() { git show-ref --verify --quiet "refs/heads/$1" || git show-ref --verify --quiet "refs/remotes/origin/$1" || git ls-remote --exit-code --heads origin "$1" >/dev/null 2>&1; }

_flow_start_worktree() {
  local feature="$1" agent="$2" base="$3" wt_dir="wt-${agent}-${feature}" branch="${agent}/${feature}"
  log_step "Creating worktree ${CYAN}${wt_dir}${NC} from ${base}"
  if typeset -f wtnew &>/dev/null; then
    wtnew "$feature" "$agent" "$base" || { log_error "wtnew failed"; return 1; }
  else
    git fetch origin "$base" --quiet 2>/dev/null || true
    git worktree add -b "$branch" "../$wt_dir" "$base" || { log_error "git worktree add failed"; return 1; }
    cd "../$wt_dir" || return 1
  fi
  _flow_set_identity "$agent" || return 1
  mkdir -p docs/prds
  [[ -f "docs/prds/${feature}.md" ]] || { printf "# PRD: %s\n## 背景\n_TODO: 描述为什么需要这个功能_\n## 目标\n_TODO: 描述功能目标_\n## 需求清单\n- [ ] 需求1\n- [ ] 需求2\n" "${feature}" > "docs/prds/${feature}.md"; log_info "Created PRD stub: docs/prds/${feature}.md"; }
  if typeset -f vup &>/dev/null && [[ -n "${TMUX:-}" ]]; then vup "$wt_dir" "$agent" 2>/dev/null && log_info "tmux workspace created"; fi
  if [[ -x "bin/setup" ]]; then log_step "Executing project setup hook: bin/setup"; ./bin/setup || log_warn "Setup hook 'bin/setup' failed"
  elif [[ -x "install.sh" ]]; then log_step "Executing project setup hook: install.sh"; ./install.sh || log_warn "Setup hook 'install.sh' failed"; fi
  echo ""; log_success "Feature started: ${BOLD}${feature}${NC}"; echo "  Directory : ${CYAN}$PWD${NC}"; echo "  Branch    : ${CYAN}${branch}${NC}"; echo ""
  echo "${BOLD}Onboarding:${NC} ✅ 工作区已就绪"; echo "  为保证不产生垃圾代码，请在 AI 助手中输入: ${CYAN}/vibe-new ${feature}${NC}"; echo "  然后按 Vibe Guard 流程推进开发，完成后执行: ${CYAN}vibe flow review${NC}"
}

_flow_is_main_worktree() {
  # 检查当前目录是否是 main worktree（不是 wt-* 格式）
  local dir
  dir=$(basename "$PWD")
  [[ "$dir" =~ ^wt-[^-]+-.+$ ]] && return 1 || return 0
}

_flow_start_task() {
  local task_id="$1" agent="$2" base="$3" registry_file title branch
  vibe_require git jq || return 1

  # 保护 main worktree：禁止在 main 目录直接切换分支
  if _flow_is_main_worktree; then
    log_error "Cannot start task in main worktree"
    echo ""
    echo "${BOLD}Correct usage:${NC}"
    echo "  ${CYAN}vibe flow start <feature>${NC}        Create a new worktree for feature development"
    echo "  ${CYAN}vibe flow start --task <id>${NC}      Switch branch in existing worktree only"
    echo ""
    echo "${BOLD}Example:${NC}"
    echo "  vibe flow start refactor                    # Creates wt-claude-refactor/"
    echo "  cd ../wt-claude-refactor"
    echo "  vibe flow start --task 2026-03-02-xxx       # Now safe to switch branches"
    return 1
  fi

  registry_file="$(_flow_registry_file)"; [[ -f "$registry_file" ]] || { log_error "Missing registry.json"; return 1; }
  title="$(_flow_task_title "$task_id" "$registry_file")"; [[ -n "$title" ]] || { log_error "Task not found: $task_id"; return 1; }
  _flow_require_clean_worktree || return 1
  _flow_require_base_ref "$base" || return 1
  branch="${agent}/${task_id}"
  _flow_branch_exists "$branch" && { log_error "Target branch already exists: $branch"; return 1; }
  git checkout -b "$branch" "origin/$base" || { log_error "Failed to switch branch"; return 1; }
  _flow_set_identity "$agent" || return 1
  echo ""; log_success "Task started: ${BOLD}${task_id}${NC}"; echo "  Title     : ${title}"; echo "  Directory : ${CYAN}$PWD${NC}"; echo "  Branch    : ${CYAN}${branch}${NC}"
}

_flow_start() {
  local feature="" task_id="" agent="" base="main" arg
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_start_usage; return 0; }; done
  while [[ $# -gt 0 ]]; do
    arg="$1"
    case "$arg" in
      --task) [[ $# -ge 2 ]] || { log_error "$(_flow_start_usage)"; return 1; }; task_id="$2"; shift 2 ;;
      --task=*) task_id="${arg#*=}"; shift ;;
      --agent) [[ $# -ge 2 ]] || { log_error "$(_flow_start_usage)"; return 1; }; agent="$2"; shift 2 ;;
      --agent=*) agent="${arg#*=}"; shift ;;
      --base) [[ $# -ge 2 ]] || { log_error "$(_flow_start_usage)"; return 1; }; base="$2"; shift 2 ;;
      --base=*) base="${arg#*=}"; shift ;;
      *) [[ -z "$feature" ]] && feature="$arg"; shift || break ;;
    esac
  done
  [[ -n "$task_id" && -z "$agent" ]] && agent="$(_flow_default_agent)"
  [[ -z "$task_id" && -z "$agent" ]] && agent="${VIBE_AGENT:-claude}"
  [[ -n "$task_id" ]] && { _flow_start_task "$task_id" "$agent" "$base"; return $?; }
  [[ -n "$feature" ]] || { log_error "$(_flow_start_usage)"; return 1; }
  _flow_start_worktree "$feature" "$agent" "$base"
}

_flow_review() {
  local feature="${1:-$(_detect_feature || true)}" stats
  [[ -z "$feature" ]] && { log_error "Not in a worktree. Specify: vibe flow review <feature>"; return 1; }
  echo "\n${BOLD}${YELLOW}Pre-PR Checklist: ${feature}${NC}"; echo "  [ ] Tests pass            [ ] Error handling appropriate"; echo "  [ ] No debug artefacts    [ ] Documentation updated"; echo "  [ ] LOC ceiling (≤200/file)  [ ] No sensitive data"
  stats=$(git diff --stat HEAD 2>/dev/null); [[ -n "$stats" ]] && { echo "${BOLD}Uncommitted changes:${NC}"; echo "$stats"; }
  if vibe_has lazygit; then confirm_action "Open lazygit for code review?" && lazygit; else log_info "Tip: install lazygit for interactive review"; git status --short; fi
  echo "\n  Next → ${CYAN}vibe flow pr${NC}"
}

_flow_pr() {
  local feature="${1:-$(_detect_feature || true)}" title body
  [[ -z "$feature" ]] && { log_error "Not in a worktree"; return 1; }
  vibe_has gh || { log_error "GitHub CLI (gh) required — brew install gh"; return 1; }
  title="feat(${feature}): summary"; body="## Changes\n$(git log --oneline main..HEAD 2>/dev/null | sed 's/^/- /')\n\n## Checklist\n- [ ] Tests pass\n- [ ] Docs updated\n- [ ] Code reviewed"
  mkdir -p temp; echo "$body" > "temp/pr-${feature}.md"; log_info "PR description → temp/pr-${feature}.md"; echo ""
  if confirm_action "Create PR '${title}' now?"; then if gh pr create --title "$title" --body-file "temp/pr-${feature}.md"; then log_success "PR created! ⚠️  Merge 后记得: /vibe-done 收口大盘 + vibe flow done 清理沙盒"; else log_error "PR creation failed"; fi; fi
  echo "\n  After merge → ${CYAN}vibe flow done${NC}"
}

_flow_done() {
  local feature="${1:-$(_detect_feature || true)}" wt_dir main_dir
  [[ -z "$feature" ]] && { log_error "Not in a worktree"; return 1; }
  wt_dir=$(basename "$PWD")
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then log_warn "Uncommitted changes detected"; confirm_action "Discard and remove worktree anyway?" || { log_info "Aborted."; return 1; }; fi
  main_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); main_dir="${main_dir%/.git}"; cd "$main_dir" || { log_error "Cannot navigate to main repo"; return 1; }
  log_step "Removing worktree ${CYAN}${wt_dir}${NC}"
  git worktree remove "$wt_dir" --force 2>/dev/null || git worktree remove "../$wt_dir" --force 2>/dev/null || { log_error "Failed to remove worktree"; return 1; }
  log_success "Worktree ${wt_dir} removed — now in: ${CYAN}$PWD${NC}"; log_info "Tip: 记得在 AI 助手中执行 /vibe-done 结算大盘。"
}

_flow_sync() {
  local current_branch has_fail=0 wt_branch behind
  current_branch=$(git branch --show-current 2>/dev/null); [[ -z "$current_branch" ]] && { log_error "Not in a git repository"; return 1; }
  log_step "Syncing from source branch: ${CYAN}$current_branch${NC}"
  while read -r wt_path; do
    wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null); [[ "$wt_branch" == "$current_branch" ]] && continue
    behind=$(git rev-list --count "$wt_branch".."$current_branch" 2>/dev/null || echo "0")
    if [[ "$behind" -gt 0 ]]; then
      echo "  -> ${CYAN}$wt_branch${NC} is behind by $behind commits. Merging..."
      if git -C "$wt_path" merge "$current_branch" --no-edit >/dev/null 2>&1; then log_success "  -> Synced $wt_branch"; else log_error "  -> Merge failed for $wt_branch. Manual resolution required in $wt_path"; has_fail=1; fi
    fi
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')
  [[ "$has_fail" -eq 1 ]] && { log_error "Sync completed with failures."; return 1; }; log_success "Sync complete."
}

_flow_status() {
  local feature="${1:-$(_detect_feature || true)}" commits changed
  [[ -z "$feature" ]] && { log_error "Not in a worktree"; return 1; }
  echo "\n${BOLD}${YELLOW}Workflow Status: ${feature}${NC}"; echo "  Agent     : Agent-${(C)$(_detect_agent)}"; echo "  Branch    : ${CYAN}$(git branch --show-current 2>/dev/null)${NC}"; echo "  Directory : ${CYAN}${PWD}${NC}"
  commits=$(git log --oneline -5 2>/dev/null); [[ -n "$commits" ]] && { echo "\n${BOLD}Recent commits:${NC}"; echo "$commits" | sed 's/^/  /'; }
  changed=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' '); echo "\n  Uncommitted: ${changed}"; [[ -f "docs/prds/${feature}.md" ]] && echo "  PRD  : ✅" || echo "  PRD  : ⬜"; [[ -f "docs/specs/${feature}-spec.md" ]] && echo "  Spec : ✅" || echo "  Spec : ⬜"; echo ""
}

vibe_flow() {
  local cmd="${1:-help}"; shift 1 2>/dev/null || true
  case "$cmd" in
    start) _flow_start "$@" ;;
    review) _flow_review "$@" ;;
    pr) _flow_pr "$@" ;;
    done) _flow_done "$@" ;;
    status) _flow_status "$@" ;;
    sync) _flow_sync "$@" ;;
    *) printf "Usage: vibe flow <command>\n  start  <feature> | --task <task-id> [--agent=claude] [--base=main]  创建或重启任务流\n  review [feature]   Pre-PR 检查清单 + lazygit\n  pr     [feature]   生成 PR 并通过 gh 创建\n  done   [feature]   清理 worktree\n  status [feature]   查看 feature 状态\n  sync               同步当前分支的变更到其他所有 worktree 分支\n" ;;
  esac
}
