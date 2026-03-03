#!/usr/bin/env bats
# Integration tests with control plane execution intent

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/worktree.sh"
  source "$VIBE_ROOT/config/aliases/tmux.sh"
  source "$VIBE_ROOT/config/aliases/execution-contract.sh"

  # Use unique task IDs for test isolation
  export TEST_TASK_A="integration-a-$$"
  export TEST_TASK_B="integration-b-$$"
}

teardown() {
  # Cleanup test artifacts
  wtrm "wt-claude-$TEST_TASK_A" --force 2>/dev/null || true
  wtrm "wt-claude-$TEST_TASK_B" --force 2>/dev/null || true
  tmkill "claude-$TEST_TASK_A" --force 2>/dev/null || true
  tmkill "claude-$TEST_TASK_B" --force 2>/dev/null || true
}

@test "Integration: Control plane execution intent consumption" {
  # Simulate control plane providing execution intent
  local task_id="$TEST_TASK_A"
  local worktree_hint="wt-claude-$TEST_TASK_A"
  local session_hint="claude-$TEST_TASK_A"

  # Create based on hints
  wtnew "$TEST_TASK_A" claude main || true
  tmnew "$TEST_TASK_A" claude || true

  # Write execution result
  write_execution_result "$task_id" "$worktree_hint" "$session_hint"

  # Control plane should be able to query
  local result
  result=$(query_by_task_id "$task_id")

  # Verify contract
  local resolved_worktree resolved_session
  resolved_worktree=$(echo "$result" | jq -r '.resolved_worktree')
  resolved_session=$(echo "$result" | jq -r '.resolved_session')

  [ "$resolved_worktree" == "$worktree_hint" ]
  [ "$resolved_session" == "$session_hint" ]
}

@test "Integration: Cross-worktree execution result access" {
  # Save original directory (project root)
  local orig_dir="$(pwd)"

  # Create from worktree A and save its path (wtnew cds into it)
  wtnew "$TEST_TASK_A" claude main || true
  local wt_path_a="$(pwd)"
  cd "$orig_dir" || return 1  # Return to original dir

  # Create from worktree B and save its path
  wtnew "$TEST_TASK_B" claude main || true
  local wt_path_b="$(pwd)"
  cd "$orig_dir" || return 1  # Return to original dir

  # Write result from A (from project root)
  write_execution_result "task-$$-a" "wt-claude-$TEST_TASK_A" "claude-$TEST_TASK_A" || true

  # Query from project root (not from B) should succeed
  run query_by_task_id "task-$$-a"
  [ "$status" -eq 0 ]
  [[ "$output" == *"task-$$-a"* ]]
}

@test "Integration: Execution result update propagation" {
  # Create environment
  local task_id="update-test-$$"
  wtnew "$task_id" claude main || true
  write_execution_result "$task_id" "wt-claude-$task_id" "claude-$task_id" || true

  # Update worktree name
  update_execution_result "$task_id" "resolved_worktree" "wt-claude-updated-$$" || true

  # Verify update
  local result
  result=$(query_by_task_id "$task_id")
  local wt
  wt=$(echo "$result" | jq -r '.resolved_worktree')
  [ "$wt" == "wt-claude-updated-$$" ]
}
