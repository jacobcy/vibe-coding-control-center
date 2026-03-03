#!/usr/bin/env zsh
# Execution contract query functions
# Part of V3 Execution Plane

EXECUTION_RESULTS_DIR="${EXECUTION_RESULTS_DIR:-.agent/execution-results}"

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
