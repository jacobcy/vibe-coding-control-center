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



_flow_capture_dirty_state() {
  local operation="$1" target_branch="$2" dirty="" nonce="" stash_message="" stash_ref="" stash_oid=""
  dirty="$(git status --porcelain 2>/dev/null || true)"
  [[ -n "$dirty" ]] || return 0

  nonce="$(date +%s)-$$-${RANDOM:-0}"
  stash_message="vibe-flow:${operation}:${target_branch}:${nonce}"
  git stash push -u -m "$stash_message" >/dev/null || {
    log_error "Failed to stash changes"
    return 1
  }

  stash_oid="$(git rev-parse -q --verify refs/stash 2>/dev/null || true)"
  [[ -n "$stash_oid" ]] || {
    log_error "Failed to resolve saved stash object for ${operation}: ${target_branch}"
    return 1
  }

  stash_ref="$(git stash list --format='%H %gd' | awk -v oid="$stash_oid" '$1 == oid { print $2; exit }')"
  [[ -n "$stash_ref" ]] || {
    log_error "Failed to locate saved stash ref for ${operation}: ${target_branch}. Saved changes remain in stash object $stash_oid"
    return 1
  }

  printf '%s\n' "$stash_ref"
}

_flow_restore_captured_state() {
  local stash_ref="$1" context="$2"
  [[ -n "$stash_ref" ]] || return 0

  git stash apply "$stash_ref" || {
    log_error "Failed to restore saved changes from $stash_ref during $context. Resolve manually with: git stash apply $stash_ref"
    return 1
  }

  git stash drop "$stash_ref" || {
    log_error "Restored changes from $stash_ref but failed to drop it. Clean it up manually."
    return 1
  }
}

_flow_restore_source_state() {
  local restore_branch="$1" stash_ref="$2" context="$3" restore_ref="${4:-}"

  if [[ -n "$restore_branch" ]]; then
    git checkout "$restore_branch" || {
      log_error "Failed to restore original branch: $restore_branch"
      [[ -n "$stash_ref" ]] && log_error "Saved changes remain in $stash_ref"
      return 1
    }
  elif [[ -n "$restore_ref" ]]; then
    git checkout --detach "$restore_ref" || {
      log_error "Failed to restore original detached HEAD: $restore_ref"
      [[ -n "$stash_ref" ]] && log_error "Saved changes remain in $stash_ref"
      return 1
    }
  fi

  _flow_restore_captured_state "$stash_ref" "$context"
}

_flow_switch() {
  local target="" arg current_branch branch_name existing_ref="" stash_ref=""
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_switch_usage; return 0; }; done

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -*) log_error "Unknown option for flow switch: $1"; _flow_switch_usage; return 1 ;;
      *) [[ -z "$target" ]] && target="$1"; shift ;;
    esac
  done

  [[ -n "$target" ]] || { _flow_switch_usage; return 1; }
  current_branch="$(git branch --show-current 2>/dev/null)"
  [[ -n "$current_branch" ]] || { log_error "Not on a branch."; return 1; }
  case "$current_branch" in
    main|master)
      log_error "Refusing to rotate protected branch: $current_branch"
      return 1
      ;;
  esac

  branch_name="$(_flow_switch_target_branch "$target")"
  _flow_history_has_closed_feature "$target" && { log_error "Flow already existed and was closed: $(_flow_feature_slug "$target")"; return 1; }
  git check-ref-format --branch "$branch_name" >/dev/null 2>&1 || { log_error "Invalid branch name: $branch_name"; return 1; }
  [[ "$branch_name" != "$current_branch" ]] || { log_error "Target branch matches current branch: $current_branch"; return 1; }

  stash_ref="$(_flow_capture_dirty_state switch "$branch_name")" || return 1

  if _flow_branch_has_pr "$branch_name"; then
    _flow_restore_source_state "" "$stash_ref" "flow switch preflight"
    log_error "Flow '$branch_name' already has PR history and cannot be resumed via switch."
    return 1
  fi

  existing_ref="$(_flow_branch_ref "$branch_name" 2>/dev/null)" || {
    _flow_restore_source_state "" "$stash_ref" "flow switch preflight"
    log_error "Flow branch not found: $branch_name"
    return 1
  }

  log_step "Switching to existing flow branch: $branch_name"
  if [[ "$existing_ref" == "$branch_name" ]]; then
    git checkout "$branch_name" || {
      _flow_restore_source_state "" "$stash_ref" "flow switch to $branch_name"
      log_error "Failed to checkout branch: $branch_name"
      return 1
    }
  else
    git checkout -b "$branch_name" "$existing_ref" || {
      _flow_restore_source_state "" "$stash_ref" "flow switch to $branch_name"
      log_error "Failed to materialize branch from: $existing_ref"
      return 1
    }
  fi

  _flow_update_current_worktree_branch "$branch_name" || {
    log_error "Failed to update worktree runtime state"
    _flow_restore_source_state "$current_branch" "$stash_ref" "flow switch to $branch_name"
    return 1
  }

  if [[ -n "$stash_ref" ]]; then
    log_step "Restoring saved changes into $branch_name"
    _flow_restore_captured_state "$stash_ref" "flow switch to $branch_name" || return 1
  fi

  log_success "Flow runtime ready: $target (branch: $branch_name)"
}

_flow_update_current_worktree_branch() {
  local new_branch="$1" wt_path wt_name common_dir worktrees_file tmp now
  wt_path="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
  wt_name="$(basename "$wt_path")"
  common_dir="$(vibe_git_dir 2>/dev/null)" || return 0
  worktrees_file="$common_dir/vibe/worktrees.json"
  [[ -f "$worktrees_file" ]] || return 0
  now="$(_flow_now_iso)"
  tmp="$(mktemp)" || return 1
  jq --arg name "$wt_name" --arg path "$wt_path" --arg branch "$new_branch" --arg now "$now" '
    if any(.worktrees[]?; .worktree_name == $name) then
      .worktrees = [.worktrees[] | if .worktree_name == $name then
        (if .branch != $branch then .current_task = null | .tasks = [] else . end)
        | .branch = $branch | .status = "active" | .last_updated = $now
      else . end]
    else
      .worktrees += [{"worktree_name":$name,"worktree_path":$path,"branch":$branch,"status":"active","last_updated":$now}]
    end
  ' "$worktrees_file" > "$tmp" && mv "$tmp" "$worktrees_file" || { rm -f "$tmp"; return 1; }
}
