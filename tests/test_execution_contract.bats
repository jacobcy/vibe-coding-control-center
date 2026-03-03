#!/usr/bin/env bats
# Tests for V3 Execution Plane - Execution Contract

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/execution-contract.sh"
  export EXECUTION_RESULTS_DIR=".agent/execution-results"
  mkdir -p "$EXECUTION_RESULTS_DIR"
}

teardown() {
  rm -rf "$EXECUTION_RESULTS_DIR"
}

@test "get executor - human mode" {
  unset EXECUTOR
  result=$(_get_executor)
  [ "$result" == "human" ]
}

@test "get executor - openclaw mode" {
  export EXECUTOR=openclaw
  result=$(_get_executor)
  [ "$result" == "openclaw" ]
}

@test "get timestamp - ISO 8601 format" {
  timestamp=$(_get_timestamp)
  [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "validate execution result - valid JSON" {
  cat > "$EXECUTION_RESULTS_DIR/test-valid.json" << 'EOF'
{
  "task_id": "test-123",
  "resolved_worktree": "wt-claude-test",
  "resolved_session": "claude-test",
  "executor": "human",
  "timestamp": "2026-03-03T06:30:00Z"
}
EOF

  run _validate_execution_result "$EXECUTION_RESULTS_DIR/test-valid.json"
  [ "$status" -eq 0 ]
}

@test "validate execution result - missing field" {
  cat > "$EXECUTION_RESULTS_DIR/test-invalid.json" << 'EOF'
{
  "task_id": "test-123",
  "resolved_worktree": "wt-claude-test"
}
EOF

  run _validate_execution_result "$EXECUTION_RESULTS_DIR/test-invalid.json"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Missing required field"* ]]
}

@test "validate execution result - invalid executor" {
  cat > "$EXECUTION_RESULTS_DIR/test-invalid-executor.json" << 'EOF'
{
  "task_id": "test-123",
  "resolved_worktree": "wt-claude-test",
  "resolved_session": "claude-test",
  "executor": "invalid",
  "timestamp": "2026-03-03T06:30:00Z"
}
EOF

  run _validate_execution_result "$EXECUTION_RESULTS_DIR/test-invalid-executor.json"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Invalid executor value"* ]]
}

@test "write execution result - success" {
  run write_execution_result "test-456" "wt-claude-test2" "claude-test2"
  [ "$status" -eq 0 ]
  [ -f "$EXECUTION_RESULTS_DIR/test-456.json" ]
}

@test "write execution result - validates JSON" {
  run write_execution_result "test-789" "wt-claude-test3" "claude-test3"
  [ "$status" -eq 0 ]

  # Verify JSON is valid
  jq empty "$EXECUTION_RESULTS_DIR/test-789.json"
}

@test "query by task_id - found" {
  write_execution_result "test-query" "wt-claude-query" "claude-query" || true

  run query_by_task_id "test-query"
  [ "$status" -eq 0 ]
  [[ "$output" == *"test-query"* ]]
}

@test "query by task_id - not found" {
  run query_by_task_id "nonexistent"
  [ "$status" -eq 1 ]
  [[ "$output" == *"not found"* ]]
}

@test "query by worktree - found" {
  write_execution_result "test-wt" "wt-claude-find" "claude-find" || true

  run query_by_worktree "wt-claude-find"
  [ "$status" -eq 0 ]
  [[ "$output" == *"wt-claude-find"* ]]
}

@test "query by session - found" {
  write_execution_result "test-sess" "wt-claude-sess" "claude-sess" || true

  run query_by_session "claude-sess"
  [ "$status" -eq 0 ]
  [[ "$output" == *"claude-sess"* ]]
}

@test "update execution result - success" {
  write_execution_result "test-update" "wt-old" "old-session" || true

  run update_execution_result "test-update" "resolved_session" "new-session"
  [ "$status" -eq 0 ]

  local session
  session=$(jq -r '.resolved_session' "$EXECUTION_RESULTS_DIR/test-update.json")
  [ "$session" == "new-session" ]
}

@test "cleanup execution results - creates backup" {
  write_execution_result "test-cleanup" "wt-cleanup" "cleanup-session" || true

  local backup_dir=".agent/execution-results-backup/$(date +%Y%m%d)*"

  run cleanup_execution_results
  [ "$status" -eq 0 ]

  # Verify backup was created
  local found_backup=0
  for dir in .agent/execution-results-backup/*; do
    [[ -d "$dir" ]] && found_backup=1 && break
  done
  [ "$found_backup" -eq 1 ]
}
