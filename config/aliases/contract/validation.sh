#!/usr/bin/env zsh
# Execution contract validation utilities
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

# Validate JSON schema
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
    echo "Invalid executor value: $executor (must be 'human' or 'openclaw')"
    return 1
  fi
  
  return 0
}
