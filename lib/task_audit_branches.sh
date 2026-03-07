#!/usr/bin/env zsh
# lib/task_audit_branches.sh - Branch field audit and repair

_task_audit_branches() {
  local worktrees_file="$1"
  local -a null_branch_worktrees
  local line

  while IFS= read -r line; do
    null_branch_worktrees+=("$line")
  done < <(jq -r '.worktrees[]? | select(.branch == null or .branch == "") | .worktree_name' "$worktrees_file" 2>/dev/null)

  [[ ${#null_branch_worktrees[@]} -eq 0 ]] && return 0

  for line in "${null_branch_worktrees[@]}"; do
    echo "$line"
  done

  return ${#null_branch_worktrees[@]}
}

_task_get_worktree_branch() {
  local worktree_path="$1"
  local branch ref

  [[ -d "$worktree_path" ]] || return 1

  branch=$(git -C "$worktree_path" branch --show-current 2>/dev/null) || {
    branch=$(git -C "$worktree_path" symbolic-ref --short HEAD 2>/dev/null) || {
      ref=$(git -C "$worktree_path" rev-parse --abbrev-ref HEAD 2>/dev/null)
      [[ "$ref" != "HEAD" ]] && branch="$ref"
    }
  }

  [[ -n "$branch" ]] || return 1
  echo "$branch"
}

_task_fix_branches() {
  local worktrees_file="$1"
  local dry_run="${2:-false}"
  local backup_file="${worktrees_file}.backup"
  local rollback_needed=false
  local -a fixed_worktrees failed_worktrees null_branch_worktrees
  local line

  while IFS= read -r line; do
    null_branch_worktrees+=("$line")
  done < <(_task_audit_branches "$worktrees_file")

  if [[ ${#null_branch_worktrees[@]} -eq 0 ]]; then
    log_info "No null branch fields found in worktrees.json"
    return 0
  fi

  log_info "Found ${#null_branch_worktrees[@]} worktrees with null branch field"
  if [[ "$dry_run" != "true" ]]; then
    cp "$worktrees_file" "$backup_file"
    log_info "Created backup: $backup_file"
  fi

  local wt_name wt_path actual_branch temp_file
  for wt_name in "${null_branch_worktrees[@]}"; do
    wt_path=$(jq -r --arg name "$wt_name" '.worktrees[]? | select(.worktree_name == $name) | .worktree_path' "$worktrees_file" 2>/dev/null)

    if [[ -z "$wt_path" ]]; then
      log_warn "Could not find path for worktree: $wt_name"
      failed_worktrees+=("$wt_name (no path in worktrees.json)")
      continue
    fi

    if [[ ! -d "$wt_path" ]]; then
      log_warn "Worktree path does not exist: $wt_name ($wt_path)"
      failed_worktrees+=("$wt_name (path not found)")
      continue
    fi

    if [[ ! -e "$wt_path/.git" ]] && ! git -C "$wt_path" rev-parse --git-dir >/dev/null 2>&1; then
      log_warn "Not a valid git worktree: $wt_name ($wt_path)"
      failed_worktrees+=("$wt_name (not a git worktree)")
      continue
    fi

    actual_branch=$(_task_get_worktree_branch "$wt_path")
    if [[ -z "$actual_branch" ]]; then
      log_warn "Could not determine branch for worktree: $wt_name"
      failed_worktrees+=("$wt_name (no branch)")
      continue
    fi

    if [[ "$dry_run" == "true" ]]; then
      log_success "[DRY-RUN] Would update $wt_name: null → $actual_branch"
      fixed_worktrees+=("$wt_name")
      continue
    fi

    temp_file="${worktrees_file}.tmp"
    if jq --arg wt "$wt_name" --arg branch "$actual_branch" \
      '(.worktrees[] | select(.worktree_name == $wt) | .branch) |= $branch' \
      "$worktrees_file" > "$temp_file" && mv "$temp_file" "$worktrees_file"; then
      log_success "Fixed $wt_name: null → $actual_branch"
      fixed_worktrees+=("$wt_name")
    else
      log_error "Failed to update $wt_name"
      failed_worktrees+=("$wt_name (update failed)")
      rollback_needed=true
    fi
  done

  if [[ "$rollback_needed" == "true" && -f "$backup_file" ]]; then
    log_warn "Critical failure detected, rolling back from backup..."
    cp "$backup_file" "$worktrees_file"
    log_info "Restored from backup: $backup_file"
    return 1
  fi

  echo ""
  log_info "Summary:"
  echo "  Fixed: ${#fixed_worktrees[@]}"
  echo "  Failed: ${#failed_worktrees[@]}"

  if [[ ${#failed_worktrees[@]} -gt 0 ]]; then
    log_warn "Failed worktrees:"
    local wt
    for wt in "${failed_worktrees[@]}"; do
      echo "  - $wt"
    done
    return 1
  fi

  return 0
}
