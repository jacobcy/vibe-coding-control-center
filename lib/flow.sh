#!/usr/bin/env zsh
[[ -z "${VIBE_ROOT:-}" ]] && { echo "error: VIBE_ROOT not set"; return 1; }
source "$VIBE_LIB/flow_help.sh"
source "$VIBE_LIB/flow_history.sh"
source "$VIBE_LIB/flow_show.sh"
source "$VIBE_LIB/flow_status.sh"
source "$VIBE_LIB/flow_review.sh"
source "$VIBE_LIB/flow_pr.sh"
source "$VIBE_LIB/task.sh"
source "$VIBE_LIB/flow_runtime.sh"
_flow_registry_file() { echo "$(vibe_git_dir)/vibe/registry.json"; }
_flow_task_title() { jq -r --arg tid "$1" '.tasks[]?|select(.task_id==$tid)|.title//empty' "$2"; }
_flow_default_agent() { _detect_agent 2>/dev/null || echo "${VIBE_DEFAULT_TOOL:-claude}"; }
_flow_normalize_branch_name() {
  local ref="$1"
  case "$ref" in
    refs/remotes/origin/*) echo "${ref#refs/remotes/origin/}" ;;
    refs/heads/*) echo "${ref#refs/heads/}" ;;
    origin/*) echo "${ref#origin/}" ;;
    *) echo "$ref" ;;
  esac
}
_flow_require_base_ref() {
  local branch_name
  branch_name="$(_flow_normalize_branch_name "$1")"
  git fetch origin "$branch_name" --quiet 2>/dev/null || true
  git show-ref --verify --quiet "refs/remotes/origin/$branch_name" || { log_error "origin/$branch_name not found"; return 1; }
}
_flow_branch_exists() {
  local branch_name
  branch_name="$(_flow_normalize_branch_name "$1")"
  git show-ref --verify --quiet "refs/heads/$branch_name" || git show-ref --verify --quiet "refs/remotes/origin/$branch_name" || git ls-remote --exit-code --heads origin "$branch_name" >/dev/null 2>&1
}
_flow_is_main_worktree() { local d; d=$(basename "$PWD"); [[ "$d" =~ ^wt-[^-]+-.+$ ]] && return 1 || return 0; }
_flow_branch_ref() {
  local branch_name="${1#origin/}"
  git show-ref --verify --quiet "refs/heads/$branch_name" && { echo "$branch_name"; return 0; }
  git show-ref --verify --quiet "refs/remotes/origin/$branch_name" && { echo "origin/$branch_name"; return 0; }
  return 1
}
_flow_pr_candidate_bases() { local branch="$1"; git for-each-ref --format='%(refname:short)' refs/heads refs/remotes/origin 2>/dev/null | sed 's#^origin/##' | awk -v b="$branch" 'NF && $0 != "HEAD" && $0 != b { seen[$0]=1 } END { for (name in seen) print name }'; }
_flow_pick_pr_base() {
  local branch="$1" candidate ref best="" best_count="" ahead_count=""
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue; ref="$(_flow_branch_ref "$candidate")" || continue
    git merge-base --is-ancestor "$ref" HEAD >/dev/null 2>&1 || continue
    ahead_count=$(git rev-list --count "$ref..HEAD" 2>/dev/null) || continue
    [[ -z "$best" || "$ahead_count" -lt "$best_count" ]] && { best="$candidate"; best_count="$ahead_count"; }
  done < <(_flow_pr_candidate_bases "$branch")
  [[ -n "$best" ]] && echo "$best"
}
_flow_resolve_pr_base() {
  local requested="$1" branch="$2" inferred="" normalized=""
  if [[ -n "$requested" ]]; then
    normalized="$(_flow_normalize_branch_name "$requested")"
    _flow_branch_exists "$normalized" || { log_error "PR base not found: $requested"; return 1; }
    echo "$normalized"
    return 0
  fi
  inferred="$(_flow_pick_pr_base "$branch")"
  [[ -n "$inferred" ]] || { log_error "Unable to infer PR base. Re-run with --base <ref>."; return 1; }
  [[ "$inferred" == "main" ]] && { echo "$inferred"; return 0; }
  log_error "Refusing to default PR base to main. Current branch appears to be based on '$inferred'. Re-run with --base $inferred."
  return 1
}
_flow_pr_base_git_ref() {
  local base_name branch_name base_ref=""
  branch_name="$(_flow_normalize_branch_name "$1")"
  git fetch origin "$branch_name" --quiet 2>/dev/null || true
  git show-ref --verify --quiet "refs/remotes/origin/$branch_name" && { echo "origin/$branch_name"; return 0; }
  git show-ref --verify --quiet "refs/heads/$branch_name" && { echo "$branch_name"; return 0; }
  _flow_require_base_ref "$branch_name" || return 1
  git show-ref --verify --quiet "refs/remotes/origin/$branch_name" && { echo "origin/$branch_name"; return 0; }
  log_error "Unable to resolve local git ref for PR base: $branch_name"
  return 1
}
_flow_require_latest_pr_base() {
  local base_name="$1" base_git_ref="$2"
  git merge-base --is-ancestor "$base_git_ref" HEAD >/dev/null 2>&1 && return 0
  log_error "Current branch is not based on the latest $base_name ($base_git_ref). Pull/rebase the latest $base_name, resolve conflicts, then re-run vibe flow pr."
  return 1
}
_flow_bind() {
  local tid agent="" arg reg title
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_bind_usage; return 0; }; done
  tid="$1"; shift $(( $# > 0 ? 1 : 0 ))
  while [[ $# -gt 0 ]]; do case "$1" in --agent) agent="$2"; shift 2 ;; *) shift ;; esac; done
  [[ -z "$tid" || "$tid" =~ ^-- ]] && { _flow_bind_usage; return 1; }
  reg="$(_flow_registry_file)"; title="$(_flow_task_title "$tid" "$reg")"
  [[ -n "$title" ]] || { log_error "Task not found: $tid"; return 1; }
  agent="${agent:-$(_flow_default_agent)}"
  log_step "Identity: $agent"
  log_step "Binding $tid"; _vibe_task_update "$tid" --status "in_progress" --bind-current --agent "$agent" || return 1
  log_success "Bound: $tid ($title)"
}
_flow_new() {
  local feat="" agent="" ref="origin/main" save_unstash=0 arg branch_name feature_slug current_branch current_head="" dirty="" stash_ref="" branch_created=0
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_new_usage; return 0; }; done
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --task) log_error "Use: vibe flow bind $2"; return 1 ;;
      --agent) agent="$2"; shift 2 ;;
      --branch) ref="$2"; shift 2 ;;
      --save-unstash) save_unstash=1; shift ;;
      --base) log_error "Unknown option: --base. Use --branch <ref> for the source branch when creating a flow."; return 1 ;;
      -*) log_error "Unknown option for flow new: $1"; _flow_new_usage; return 1 ;;
      *) [[ -z "$feat" ]] && feat="$1"; shift ;;
    esac
  done
  [[ -n "$feat" ]] || { _flow_new_usage; return 1; }
  current_branch="$(git branch --show-current 2>/dev/null)"
  current_head="$(git rev-parse --verify HEAD 2>/dev/null || true)"
  branch_name="$(_flow_switch_target_branch "$feat")"
  feature_slug="$(_flow_feature_slug "$branch_name")"
  _flow_history_has_closed_feature "$feature_slug" && { log_error "Flow already existed and was closed: $feature_slug"; return 1; }
  git check-ref-format --branch "$branch_name" >/dev/null 2>&1 || { log_error "Invalid branch name: $branch_name"; return 1; }
  [[ "$branch_name" != "$current_branch" ]] || { log_error "Target branch matches current branch: $current_branch"; return 1; }
  if _flow_branch_exists "$branch_name"; then
    if _flow_branch_has_pr "$branch_name"; then
      log_error "Flow '$feature_slug' already has PR history and must be closed through skill handoff."
    else
      log_error "Flow '$feature_slug' already exists. Use: vibe flow switch $feature_slug"
    fi
    return 1
  fi

  dirty="$(git status --porcelain 2>/dev/null || true)"
  if [[ -n "$dirty" && $save_unstash -ne 1 ]]; then
    log_error "Working directory is not clean. Re-run with --save-unstash to carry changes into the next flow."
    return 1
  fi
  if [[ -n "$dirty" ]]; then
    log_step "Saving uncommitted changes for flow new"
    stash_ref="$(_flow_capture_dirty_state new "$branch_name")" || return 1
  fi

  log_step "Creating flow branch: $branch_name from $ref"
  git checkout -b "$branch_name" "$ref" || {
    _flow_restore_source_state "" "$stash_ref" "flow new to $branch_name"
    log_error "Failed to create branch: $branch_name"
    return 1
  }
  branch_created=1

  _flow_update_current_worktree_branch "$branch_name" || {
    log_error "Failed to update worktree runtime state"
    _flow_restore_source_state "$current_branch" "$stash_ref" "flow new to $branch_name" "$current_head"
    git branch -D "$branch_name" 2>/dev/null || true
    return 1
  }

  if [[ -n "$stash_ref" ]]; then
    log_step "Restoring saved changes into $branch_name"
    _flow_restore_captured_state "$stash_ref" "flow new to $branch_name" || return 1
  fi
  log_success "Flow runtime ready: $feat (branch: $branch_name)"
  if [[ -n "$agent" ]]; then
    echo "💡 Agent hint: $agent"
  fi
}

# Load flow done functions
source "$VIBE_LIB/flow_done.sh"

_flow_sync() {
  log_error "vibe flow sync no longer supports cross-worktree branch merges."
  echo "Use explicit git merge/rebase in the target branch when needed."
  return 1
}

vibe_flow() {
  case "${1:-help}" in
    start|new|create) shift; _flow_new "$@" ;;
    switch) shift; _flow_switch "$@" ;;
    bind) shift; _flow_bind "$@" ;;
    done) shift; _flow_done "$@" ;;
    show) shift; _flow_show "$@" ;;
    status) shift; _flow_status "$@" ;;
    list) shift; _flow_list "$@" ;;
    sync) _flow_sync ;;
    pr) shift; _flow_pr "$@" ;;
    review) shift; _flow_review "$@" ;;
    *) _flow_usage ;;
  esac
}
