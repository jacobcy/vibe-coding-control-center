#!/usr/bin/env zsh
# Execution Contract - Standardized execution result management
# Part of V3 Execution Plane

# Constants
EXECUTION_RESULTS_DIR="${EXECUTION_RESULTS_DIR:-.agent/execution-results}"
RECOVERY_HISTORY_LOG="${RECOVERY_HISTORY_LOG:-.agent/recovery-history.log}"

# Ensure directory exists
[[ -d "$EXECUTION_RESULTS_DIR" ]] || mkdir -p "$EXECUTION_RESULTS_DIR"

# Helper: Get executor mode (human vs openclaw)
_get_executor() {
  echo "${EXECUTOR:-human}"
}

# Helper: Get ISO 8601 timestamp
_get_timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Helper: Validate JSON schema
_validate_execution_result() {
  local json_file="$1"
  
  # Check file exists
  [[ -f "$json_file" ]] || { echo "File not found: $json_file"; return 1; }
  
  # Check valid JSON
  jq empty "$json_file" 2>/dev/null || { echo "Invalid JSON: $json_file"; return 1; }
  
  # Check required fields
  local required_fields=("task_id" "resolved_worktree" "resolved_session" "executor" "timestamp")
  for field in "${required_fields[@]}"; do
    if ! jq -e ".$field" "$json_file" >/dev/null 2>&1; then
      echo "Missing required field: $field"
      return 1
    fi
  done
  
  # Check executor value
  local executor
  executor=$(jq -r '.executor' "$json_file")
  if [[ "$executor" != "human" && "$executor" != "openclaw" ]]; then
    echo "Invalid executor value: $executor (must be human or openclaw)"
    return 1
  fi
  
  return 0
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

# Query execution result by task_id
query_by_task_id() {
  local task_id="$1"
  [[ -z "$task_id" ]] && { echo "Usage: query_by_task_id <task_id>"; return 1; }
  
  local result_file="$EXECUTION_RESULTS_DIR/${task_id}.json"
  
  if [[ -f "$result_file" ]]; then
    cat "$result_file"
  else
    echo "Execution result not found for task_id: $task_id"
    return 1
  fi
}

# Query execution result by worktree
query_by_worktree() {
  local worktree="$1"
  [[ -z "$worktree" ]] && { echo "Usage: query_by_worktree <worktree>"; return 1; }
  
  local found=0
  for json_file in "$EXECUTION_RESULTS_DIR"/*.json; do
    [[ -f "$json_file" ]] || continue
    
    local wt
    wt=$(jq -r '.resolved_worktree' "$json_file" 2>/dev/null)
    
    if [[ "$wt" == "$worktree" || "$wt" == *"$worktree"* ]]; then
      cat "$json_file"
      found=1
      break
    fi
  done
  
  [[ $found -eq 0 ]] && {
    echo "Execution result not found for worktree: $worktree"
    return 1
  }
}

# Query execution result by session
query_by_session() {
  local session="$1"
  [[ -z "$session" ]] && { echo "Usage: query_by_session <session>"; return 1; }
  
  local found=0
  for json_file in "$EXECUTION_RESULTS_DIR"/*.json; do
    [[ -f "$json_file" ]] || continue
    
    local sess
    sess=$(jq -r '.resolved_session' "$json_file" 2>/dev/null)
    
    if [[ "$sess" == "$session" ]]; then
      cat "$json_file"
      found=1
      break
    fi
  done
  
  [[ $found -eq 0 ]] && {
    echo "Execution result not found for session: $session"
    return 1
  }
}

# Update execution result
update_execution_result() {
  local task_id="$1" field="$2" value="$3"
  
  [[ -z "$task_id" || -z "$field" || -z "$value" ]] && {
    echo "Usage: update_execution_result <task_id> <field> <value>"
    return 1
  }
  
  local result_file="$EXECUTION_RESULTS_DIR/${task_id}.json"
  
  [[ -f "$result_file" ]] || {
    echo "Execution result not found: $result_file"
    return 1
  }
  
  # Update field
  local tmp_file="${result_file}.tmp"
  jq ".$field = \"$value\"" "$result_file" > "$tmp_file" && mv "$tmp_file" "$result_file"
  
  echo "✓ Updated $field in $result_file"
}

# Cleanup execution results for archived tasks
cleanup_execution_results() {
  local backup_dir="${1:-.agent/execution-results-backup/$(date +%Y%m%d_%H%M%S)}"
  
  # Create backup directory
  mkdir -p "$backup_dir"
  
  # Backup and remove old results
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

echo "✓ Execution contract module loaded"
