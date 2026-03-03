#!/usr/bin/env zsh
# Execution contract maintenance utilities
# Part of V3 Execution Plane

EXECUTION_RESULTS_DIR="${EXECUTION_RESULTS_DIR:-.agent/execution-results}"
RECOVERY_HISTORY_LOG="${RECOVERY_HISTORY_LOG:-.agent/recovery-history.log}"

# Cleanup execution results for archived tasks
cleanup_execution_results() {
  local backup_dir="${1:-.agent/execution-results-backup/$(date +%Y%m%d_%H%M%S)}"
  
  # Create backup directory
  mkdir -p "$backup_dir"
  
  # Backup and remove old results (placeholder - would need task status integration)
  local count=0
  for json_file in "$EXECUTION_RESULTS_DIR"/*.json; do
    [[ -f "$json_file" ]] || continue
    
    # TODO: Check task status from control plane
    # For now, just backup all files
    cp "$json_file" "$backup_dir/"
    ((count++))
  done
  
  echo "✓ Backed up $count execution results to $backup_dir"
}

# Write execution result
write_execution_result() {
  local task_id="$1" worktree="$2" session="$3"
  
  [[ -z "$task_id" || -z "$worktree" || -z "$session" ]] && {
    echo "Usage: write_execution_result <task_id> <worktree> <session>"
    return 1
  }
  
  local result_file="$EXECUTION_RESULTS_DIR/${task_id}.json"
  local executor timestamp
  
  executor=$(_get_executor)
  timestamp=$(_get_timestamp)
  
  # Write JSON using jq for proper escaping
  jq -n \
    --arg tid "$task_id" \
    --arg wt "$worktree" \
    --arg sess "$session" \
    --arg exec "$executor" \
    --arg ts "$timestamp" \
    '{
      task_id: $tid,
      resolved_worktree: $wt,
      resolved_session: $sess,
      executor: $exec,
      timestamp: $ts
    }' > "$result_file"
  
  # Validate
  if _validate_execution_result "$result_file"; then
    echo "✓ Execution result written: $result_file"
    return 0
  else
    echo "✗ Failed to validate execution result"
    rm -f "$result_file"
    return 1
  fi
}
