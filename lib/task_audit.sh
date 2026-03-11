#!/usr/bin/env zsh
# lib/task_audit.sh - Task registry audit orchestration
source "$VIBE_LIB/task_audit_checks.sh"
_task_generate_audit_summary() {
  local common_dir="$1"
  local worktrees_file="$common_dir/vibe/worktrees.json"
  local -a data_quality_issues registration_issues sync_issues

  echo ""
  log_step "Audit Summary Report"
  echo ""

  # Data Quality check removed since branches are the single source of truth


  log_info "=== Task Registration Issues ==="
  local -a unregistered_branches
  local line
  while IFS= read -r line; do
    unregistered_branches+=("$line")
  done < <(_task_check_branch_registration "$common_dir")

  if [[ ${#unregistered_branches[@]} -eq 0 ]]; then
    log_success "✓ All branch tasks are registered"
  else
    log_warn "✗ ${#unregistered_branches[@]} unregistered branch tasks found"
    local wt_name branch pattern entry
    for entry in "${unregistered_branches[@]}"; do
      wt_name=$(echo "$entry" | cut -d'|' -f1)
      branch=$(echo "$entry" | cut -d'|' -f2)
      pattern=$(echo "$entry" | cut -d'|' -f3)
      echo "    - $wt_name (branch: $branch, pattern: $pattern)"
    done
    log_info "  Action: Review and register tasks as needed"
    registration_issues+=("unregistered_branches")
  fi
  echo ""

  log_info "=== OpenSpec Sync Issues ==="
  local -a unsynced_changes
  while IFS= read -r line; do
    [[ "$(echo "$line" | cut -d'|' -f5)" == "false" ]] && unsynced_changes+=("$line")
  done < <(_task_check_openspec_sync "$common_dir")

  if [[ ${#unsynced_changes[@]} -eq 0 ]]; then
    log_success "✓ All OpenSpec changes are synced"
  else
    log_warn "✗ ${#unsynced_changes[@]} unsynced OpenSpec changes found"
    local name has_tasks total done entry
    for entry in "${unsynced_changes[@]}"; do
      name=$(echo "$entry" | cut -d'|' -f1)
      has_tasks=$(echo "$entry" | cut -d'|' -f2)
      total=$(echo "$entry" | cut -d'|' -f3)
      done=$(echo "$entry" | cut -d'|' -f4)
      if [[ "$has_tasks" == "true" && "$total" -gt 0 ]]; then
        echo "    - $name (tasks: $done/$total completed)"
      else
        echo "    - $name"
      fi
    done
    log_info "  Action: Register these OpenSpec changes as tasks"
    sync_issues+=("unsynced_changes")
  fi
  echo ""

  log_step "Overall Health Status"
  local total_issues=$(( ${#data_quality_issues[@]} + ${#registration_issues[@]} + ${#sync_issues[@]} ))
  if [[ "$total_issues" -eq 0 ]]; then
    log_success "✓✓✓ All checks passed! Task registry is healthy."
    return 0
  fi

  log_warn "✗✗✗ Found $total_issues category(s) with issues"
  echo ""
  log_info "Next Steps:"
  [[ ${#registration_issues[@]} -gt 0 ]] && echo "  1. Review unregistered tasks and register as needed"
  [[ ${#sync_issues[@]} -gt 0 ]] && echo "  2. Register OpenSpec changes as tasks"
  return 1
}

vibe_task_audit() {
  local dry_run=false check_branches=false check_openspec=false check_plans=false all_checks=false
  local common_dir worktrees_file
  local -a unregistered_branches unsynced_changes untracked_files
  local line wt_name branch pattern name has_tasks total done entry type file

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run=true; shift ;;
      --check-branches) check_branches=true; shift ;;
      --check-openspec) check_openspec=true; shift ;;
      --check-plans) check_plans=true; shift ;;
      --all) all_checks=true; shift ;;
      -h|--help) _task_audit_usage; return 0 ;;
      *) log_error "Unknown option: $1"; _task_audit_usage; return 1 ;;
    esac
  done

  common_dir="$(_vibe_task_common_dir)" || return 1
  worktrees_file="$common_dir/vibe/worktrees.json"
  _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1

  if [[ "$check_branches" == "true" || "$all_checks" == "true" ]]; then
    log_step "Phase 2: Branch Registration Check"
    unregistered_branches=()
    while IFS= read -r line; do unregistered_branches+=("$line"); done < <(_task_check_branch_registration "$common_dir")
    if [[ ${#unregistered_branches[@]} -eq 0 ]]; then
      log_success "All branch tasks are registered"
    else
      log_warn "Found ${#unregistered_branches[@]} unregistered branch tasks:"
      for entry in "${unregistered_branches[@]}"; do
        wt_name=$(echo "$entry" | cut -d'|' -f1)
        branch=$(echo "$entry" | cut -d'|' -f2)
        pattern=$(echo "$entry" | cut -d'|' -f3)
        echo "  - $wt_name (branch: $branch, pattern: $pattern)"
      done
    fi
    echo ""
  fi

  if [[ "$check_openspec" == "true" || "$all_checks" == "true" ]]; then
    log_step "Phase 2: OpenSpec Sync Check"
    unsynced_changes=()
    while IFS= read -r line; do
      [[ "$(echo "$line" | cut -d'|' -f5)" != "false" ]] && continue
      unsynced_changes+=("$line")
    done < <(_task_check_openspec_sync "$common_dir")
    if [[ ${#unsynced_changes[@]} -eq 0 ]]; then
      log_success "All OpenSpec changes are synced"
    else
      log_warn "Found ${#unsynced_changes[@]} unsynced OpenSpec changes:"
      for entry in "${unsynced_changes[@]}"; do
        name=$(echo "$entry" | cut -d'|' -f1)
        has_tasks=$(echo "$entry" | cut -d'|' -f2)
        total=$(echo "$entry" | cut -d'|' -f3)
        done=$(echo "$entry" | cut -d'|' -f4)
        [[ "$has_tasks" == "true" && "$total" -gt 0 ]] && echo "  - $name (tasks: $done/$total completed)" || echo "  - $name (no tasks.md)"
      done
      log_info "Consider registering these OpenSpec changes as tasks"
    fi
    echo ""
  fi

  if [[ "$check_plans" == "true" || "$all_checks" == "true" ]]; then
    log_step "Phase 2: Plans & PRDs Check"
    untracked_files=()
    while IFS= read -r line; do untracked_files+=("$line"); done < <(_task_check_plans_prds "$common_dir")
    if [[ ${#untracked_files[@]} -eq 0 ]]; then
      log_success "All plans and PRDs are tracked"
    else
      log_warn "Found ${#untracked_files[@]} untracked files:"
      for entry in "${untracked_files[@]}"; do
        type=$(echo "$entry" | cut -d'|' -f1)
        file=$(echo "$entry" | cut -d'|' -f2)
        echo "  - [$type] $file"
      done
      log_info "Consider converting these files to standard task format"
    fi
    echo ""
  fi

  [[ "$all_checks" == "true" ]] && _task_generate_audit_summary "$common_dir"

  if [[ "$check_branches" == "false" && "$check_openspec" == "false" && "$check_plans" == "false" && "$all_checks" == "false" ]]; then
    log_warn "No audit checks were selected."
    log_info "Use --all or specific check flags (e.g., --check-branches) to run the audit."
    return 1
  fi

  return 0
}
