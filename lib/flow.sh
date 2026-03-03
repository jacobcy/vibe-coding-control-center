#!/usr/bin/env zsh
# v2/lib/flow.sh - Flow Orchestration Module
# Target: ~100 lines | Manages feature sandbox lifecycle

[[ -z "${VIBE_ROOT:-}" ]] && { echo "error: VIBE_ROOT not set"; return 1; }

# Load sub-modules
source "$VIBE_LIB/flow_help.sh"
source "$VIBE_LIB/flow_status.sh"
source "$VIBE_LIB/task.sh"

_flow_registry_file() { echo "$(git rev-parse --git-common-dir)/vibe/registry.json"; }
_flow_task_title() { jq -r --arg task_id "$1" '.tasks[]? | select(.task_id == $task_id) | .title // empty' "$2"; }
_flow_set_identity() { git config user.name "$1" 2>/dev/null || git config user.name "$1" || return 1; git config user.email "$1@vibe.coding" 2>/dev/null || git config user.email "$1@vibe.coding"; }
_flow_default_agent() { _detect_agent 2>/dev/null || echo "${VIBE_AGENT:-claude}"; }
_flow_require_clean_worktree() { [[ -z "$(git status --porcelain 2>/dev/null)" ]] || { log_error "Refusing to start task from dirty worktree"; return 1; }; }
_flow_require_base_ref() { git fetch origin "$1" --quiet 2>/dev/null || true; git show-ref --verify --quiet "refs/remotes/origin/$1" || { log_error "origin/$1 not found"; return 1; }; }
_flow_branch_exists() { git show-ref --verify --quiet "refs/heads/$1" || git show-ref --verify --quiet "refs/remotes/origin/$1" || git ls-remote --exit-code --heads origin "$1" >/dev/null 2>&1; }
_flow_shared_dir() { local d; d="$(git rev-parse --git-common-dir)/vibe/shared"; mkdir -p "$d"; echo "$d"; }
_flow_is_main_worktree() { local d; d=$(basename "$PWD"); [[ "$d" =~ ^wt-[^-]+-.+$ ]] && return 1 || return 0; }

_flow_start_worktree() {
  local feature="$1" agent="$2" ref="$3" wt_dir="wt-${agent}-${feature}"
  vibe_require git jq || return 1

  # ① Pre-check: worktree directory must not already exist
  local repo_root; repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || { log_error "Not in a git repo"; return 1; }
  local wt_path="${repo_root:h}/$wt_dir"
  [[ -e "$wt_path" ]] && { log_error "Worktree already exists: $wt_dir (use 'wt $wt_dir' to enter)"; return 1; }

  # ② Pre-check: task must not already be registered (single source: _vibe_task helpers)
  local registry_file task_id
  registry_file="$(_flow_registry_file)"
  task_id="$(_vibe_task_today)-$(_vibe_task_slugify "$feature")"
  if [[ -f "$registry_file" ]] && jq -e --arg tid "$task_id" '.tasks[]? | select(.task_id == $tid)' "$registry_file" >/dev/null 2>&1; then
    log_error "Task already registered: $task_id (use 'vibe flow start --task $task_id' to resume)"
    return 1
  fi

  # ③ Register task into registry
  log_step "Registering task: $feature → $task_id"
  _vibe_task_add "$feature" || return 1

  # ④ Create worktree (low-level primitive — no business logic)
  log_step "Creating worktree: $wt_dir"
  if typeset -f wtnew &>/dev/null; then
    wtnew "$feature" "$agent" "$ref" || { log_error "wtnew failed"; return 1; }
  else
    git fetch origin "$ref" --quiet 2>/dev/null || true
    git worktree add -b "${agent}/${feature}" "$wt_path" "$ref" || { log_error "git worktree add failed"; return 1; }
    cd "$wt_path" || return 1
  fi

  # ⑤ Bind task to current worktree
  log_step "Binding task $task_id to worktree"
  _vibe_task_update "$task_id" --status "in_progress" --bind-current || return 1

  log_success "Feature ready: $feature  (task: $task_id)"
  echo "💡 Next: Run ${CYAN}vup${NC} to open your cockpit."
}

_flow_start_task() {
  local task_id="$1" agent="$2" ref="$3" registry_file title branch
  vibe_require git jq || return 1
  registry_file="$(_flow_registry_file)"; title="$(_flow_task_title "$task_id" "$registry_file")"
  [[ -n "$title" ]] || { log_error "Task not found: $task_id"; return 1; }
  _flow_require_clean_worktree || return 1; _flow_require_base_ref "$ref" || return 1
  branch="${agent}/${task_id}"
  _flow_branch_exists "$branch" && { log_error "Target branch already exists: $branch"; return 1; }
  git checkout -b "$branch" "origin/$ref" || return 1; _flow_set_identity "$agent" || return 1
  log_success "Started task: $task_id ($title)"
}

_flow_start() {
  local feature="" task_id="" agent="" ref="main" arg
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_start_usage; return 0; }; done
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --task) task_id="$2"; shift 2 ;;
      --agent) agent="$2"; shift 2 ;;
      --branch|--base) ref="$2"; shift 2 ;;
      *) [[ -z "$feature" ]] && feature="$1"; shift ;;
    esac
  done
  [[ -n "$task_id" && -z "$agent" ]] && agent="$(_flow_default_agent)"
  [[ -z "$task_id" && -z "$agent" ]] && agent="${VIBE_AGENT:-claude}"
  
  if [[ -n "$task_id" && -z "$feature" ]]; then
    if [[ "$(_flow_is_main_worktree; echo $?)" -eq 1 ]]; then
      # Inside a feature worktree: bind task to current
      log_step "Binding task $task_id to current worktree"
      _vibe_task_update "$task_id" --status "in_progress" --bind-current || return 1
      return 0
    else
      # In main worktree: we need a feature name to create a new worktree
      _flow_start_task "$task_id" "${agent:-claude}" "$ref"; return $?
    fi
  fi
  
  [[ -n "$feature" ]] || { _flow_start_usage; return 1; }
  _flow_start_worktree "$feature" "${agent:-claude}" "$ref"
}

_flow_done() {
  if [[ $(git branch --show-current) == "main" ]] || _flow_is_main_worktree; then
    log_warn "Current repository or branch is protected."
    return 1
  fi
  local wt_path="$PWD" wt_dir=$(basename "$wt_path") branch=$(git branch --show-current)
  log_warn "WARNING: This will clear contents of $wt_dir and PERMANENTLY delete local branch ($branch)."
  confirm_action "Proceed with cleanup?" || return 0
  local main_dir; main_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); main_dir="${main_dir%/.git}"
  cd "$main_dir" || return 1
  [[ $(git ls-remote --exit-code --heads origin "$branch" 2>/dev/null) ]] && { log_step "Deleting remote branch: $branch"; git push origin --delete "$branch" 2>/dev/null || true; }
  log_step "Detaching worktree $wt_dir"; git worktree remove "$wt_path" --force 2>/dev/null || true; mkdir -p "$wt_path"
  log_step "Cleaning up local branch: $branch"; git branch -D "$branch" 2>/dev/null || true
  log_success "Cleanup complete."
  echo "💡 Next: Run ${CYAN}vibe task list${NC} to check remaining tasks."
}

_flow_sync() {
  local current_branch has_fail=0 wt_branch behind
  current_branch=$(git branch --show-current 2>/dev/null); [[ -z "$current_branch" ]] && { log_error "Not in a git repository"; return 1; }
  while read -r wt_path; do
    wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)
    [[ "$wt_branch" == "$current_branch" ]] && continue
    behind=$(git rev-list --count "$wt_branch".."$current_branch" 2>/dev/null || echo "0")
    if [[ "$behind" -gt 0 ]]; then
      git -C "$wt_path" merge "$current_branch" --no-edit >/dev/null 2>&1 || { log_error "Merge failed for $wt_branch"; has_fail=1; }
    fi
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')
  [[ "$has_fail" -eq 1 ]] && return 1; log_success "Branches synced."
}

_flow_pr() {
  vibe_require git || return 1
  local branch; branch=$(git branch --show-current)
  [[ "$branch" == "main" ]] && { log_error "Cannot create PR from main branch"; return 1; }
  
  # ① Strict Sequential PR Check (using gh)
  if vibe_has gh; then
    log_step "Checking for existing open Pull Requests to main..."
    # Only block if there's an open PR targeting 'main' that isn't the current branch
    local open_prs; open_prs=$(gh pr list --state open --base main --json number,headRefName,title | jq -r --arg b "$branch" '.[] | select(.headRefName != $b) | "#\(.number) \(.title) (\(.headRefName))"')
    if [[ -n "$open_prs" ]]; then
      log_warn "Blocking PR creation: Another open PR to 'main' detected. Vibe requires sequential merging to 'main' to avoid version/registry conflicts."
      echo "$open_prs" | sed 's/^/  - /'
      echo "💡 Tip: Merge or close existing PRs to 'main' before submitting new changes."
      return 1
    fi
  fi

  # ② Version Management Check
  if [[ -f "VERSION" ]]; then
    local current_v; current_v=$(cat VERSION | tr -d '[:space:]')
    echo "${CYAN}Current Project Version:${NC} $current_v"
    if confirm_action "Bump project version and update CHANGELOG before pushing?"; then
       echo -n "Select bump type [patch|minor|major] (default: patch): "
       read -r bump_type
       [[ -z "$bump_type" ]] && bump_type="patch"
       ./scripts/bump.sh "$bump_type" || return 1
       git add VERSION CHANGELOG.md 2>/dev/null || true
       git commit -m "chore: bump version to $(cat VERSION)" 2>/dev/null || true
    fi
  fi

  # ③ Push and PR Create
  log_step "Pushing changes to origin/$branch"
  git push origin HEAD || return 1
  
  if vibe_has gh; then
    log_info "GitHub CLI detected. Opening PR..."
    if gh pr view "$branch" --web 2>/dev/null; then
       log_success "PR submitted! Viewed in browser."
    else
       echo "💡 Tip: Creating PR with 'gh pr create'..."
       gh pr create --fill --web || log_warn "Failed to create PR with gh, please check manually."
    fi
  else
    log_success "Changes pushed. Please create/view PR on your Git provider."
  fi
}

_flow_review() {
  vibe_require git || return 1
  local branch; branch=$(git branch --show-current)
  if vibe_has gh; then
    gh pr view "$branch" --web || { log_step "No PR found for $branch. Running local health check..."; vibe check; }
  else
    vibe check
  fi
}

vibe_flow() {
  case "${1:-help}" in
    start|new) shift; _flow_start "$@" ;;
    done)      shift; _flow_done "$@" ;;
    status)    shift; _flow_status "$@" ;;
    sync)      _flow_sync ;;
    pr)        _flow_pr ;;
    review)    _flow_review ;;
    *)         _flow_usage ;;
  esac
}
