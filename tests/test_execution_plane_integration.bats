#!/usr/bin/env bats
# Integration tests with control plane execution intent

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/worktree.sh"
  source "$VIBE_ROOT/config/aliases/tmux.sh"
  source "$VIBE_ROOT/config/aliases/execution-contract.sh"
}

@test "Integration: Control plane execution intent consumption" {
  # Simulate control plane providing execution intent
  local task_id="integration-test"
  local worktree_hint="wt-claude-integration-test"
  local session_hint="claude-integration-test"

  # Create based on hints
  wtnew integration-test claude main || true
  tmnew integration-test claude || true

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

  # Cleanup
  wtrm "$worktree_hint" --force || true
  tmkill "$session_hint" --force || true
}

@test "Integration: Cross-worktree execution result access" {
  # Create from worktree A
  wtnew cross-test-a claude main || true
  local wt_path_a="$(git rev-parse --show-toplevel:h)/wt-claude-cross-test-a"

  # Create from worktree B
  wtnew cross-test-b claude main || true
  local wt_path_b="$(git rev-parse --show-toplevel:h)/wt-claude-cross-test-b"

  # Write result from A
  cd "$wt_path_a" || return 1
  write_execution_result "task-a" "wt-claude-cross-test-a" "claude-cross-test-a" || true

  # Query from B should succeed
  cd "$wt_path_b" || return 1
  run query_by_task_id "task-a"
  [ "$status" -eq 0 ]
  [[ "$output" == *"task-a"* ]]

  # Cleanup
  cd "$wt_path_a/.." || return 1
  wtrm "wt-claude-cross-test-a" --force || true
  wtrm "wt-claude-cross-test-b" --force || true
}

@test "Integration: Execution result update propagation" {
  # Create environment
  wtnew update-test claude main || true
  write_execution_result "update-test" "wt-claude-update-test" "claude-update-test" || true

  # Update worktree name
  update_execution_result "update-test" "resolved_worktree" "wt-claude-updated" || true

  # Verify update
  local result
  result=$(query_by_task_id "update-test")
  local wt
  wt=$(echo "$result" | jq -r '.resolved_worktree')
  [ "$wt" == "wt-claude-updated" ]

  # Cleanup
  wtrm "wt-claude-update-test" --force || true
}
