#!/usr/bin/env zsh

_flow_now_iso() { date +"%Y-%m-%dT%H:%M:%S%z"; }

_flow_switch_target_branch() {
  local raw="$1" slug
  if [[ "$raw" == */* ]]; then
    echo "$raw"
    return 0
  fi
  slug="$(_vibe_task_slugify "$raw")"
  echo "task/$slug"
}

_flow_update_current_worktree_branch() {
  local branch="$1" git_common_dir worktrees_file current_dir current_path now tmp
  git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || return 0
  worktrees_file="$git_common_dir/vibe/worktrees.json"
  [[ -f "$worktrees_file" ]] || return 0

  current_dir="$(basename "$PWD")"
  current_path="$PWD"
  now="$(_flow_now_iso)"
  tmp="$(mktemp)" || return 1

  jq --arg wt "$current_dir" --arg path "$current_path" --arg branch "$branch" --arg now "$now" '
    .worktrees = (
      (.worktrees // []) as $items
      | if any($items[]?; .worktree_name == $wt or .worktree_path == $path) then
          $items | map(
            if .worktree_name == $wt or .worktree_path == $path then
              .branch = $branch
              | .worktree_name = $wt
              | .worktree_path = $path
              | .status = "active"
              | .last_updated = $now
            else . end
          )
        else
          $items + [{
            worktree_name: $wt,
            worktree_path: $path,
            branch: $branch,
            current_task: null,
            tasks: [],
            status: "active",
            dirty: false,
            agent: null,
            last_updated: $now
          }]
        end
    )
  ' "$worktrees_file" > "$tmp" && mv "$tmp" "$worktrees_file"
}

_flow_switch() {
  local forwarded=() target="" target_seen=0 save_stash=0 arg branch_name current_branch dirty="" stashed=0 existing_ref=""
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_switch_usage; return 0; }; done

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch) forwarded+=("$1" "$2"); shift 2 ;;
      --save-stash) forwarded+=("--save-unstash"); save_stash=1; shift ;;
      -*) log_error "Unknown option for flow switch: $1"; _flow_switch_usage; return 1 ;;
      *)
        if [[ $target_seen -eq 0 ]]; then
          target="$1"
          forwarded+=("$1")
          target_seen=1
        fi
        shift
        ;;
    esac
  done

  [[ $target_seen -eq 1 ]] || { _flow_switch_usage; return 1; }

  branch_name="$(_flow_switch_target_branch "$target")"
  _flow_history_has_closed_feature "$target" && { log_error "Flow already existed and was closed: $(_flow_feature_slug "$target")"; return 1; }

  if ! _flow_branch_exists "$branch_name"; then
    _flow_new "${forwarded[@]}"
    return $?
  fi

  current_branch="$(git branch --show-current 2>/dev/null)"
  [[ -n "$current_branch" ]] || { log_error "Not on a branch."; return 1; }
  [[ "$branch_name" != "$current_branch" ]] || { log_error "Target branch matches current branch: $current_branch"; return 1; }

  dirty="$(git status --porcelain 2>/dev/null || true)"
  if [[ -n "$dirty" && $save_stash -ne 1 ]]; then
    log_error "Working directory is not clean. Re-run with --save-stash to carry changes into the next flow."
    return 1
  fi

  if [[ -n "$dirty" ]]; then
    log_step "Saving uncommitted changes for flow switch"
    git stash push -u -m "Flow switch to $branch_name: saved WIP" || { log_error "Failed to stash changes"; return 1; }
    stashed=1
  fi

  if _flow_branch_has_pr "$branch_name"; then
    [[ $stashed -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
    log_error "Flow '$branch_name' already has PR history and cannot be resumed via switch."
    return 1
  fi

  existing_ref="$(_flow_branch_ref "$branch_name" 2>/dev/null)" || {
    [[ $stashed -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
    log_error "Flow branch not found: $branch_name"
    return 1
  }

  if [[ "$existing_ref" == "$branch_name" ]]; then
    git checkout "$branch_name" || {
      [[ $stashed -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
      log_error "Failed to checkout branch: $branch_name"
      return 1
    }
  else
    git checkout -b "$branch_name" "$existing_ref" || {
      [[ $stashed -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
      log_error "Failed to materialize branch from: $existing_ref"
      return 1
    }
  fi

  _flow_update_current_worktree_branch "$branch_name" || {
    [[ $stashed -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
    log_error "Failed to update worktree runtime state"
    return 1
  }

  if [[ $stashed -eq 1 ]]; then
    log_step "Restoring saved changes into $branch_name"
    git stash pop || { log_error "Stash pop failed (conflicts?). Resolve manually."; return 1; }
  fi

  log_success "Flow runtime ready: $target (branch: $branch_name)"
}
