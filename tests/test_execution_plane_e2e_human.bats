#!/usr/bin/env bats
# End-to-end tests for Execution Plane - Human Mode

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/worktree.sh"
  source "$VIBE_ROOT/config/aliases/tmux.sh"
  source "$VIBE_ROOT/config/aliases/execution-contract.sh"
  source "$VIBE_ROOT/config/aliases/session-recovery.sh"

  # Use unique task IDs for test isolation
  export TEST_TASK_ID="e2e-human-$$"
}

teardown() {
  # Cleanup test artifacts
  wtrm "wt-claude-$TEST_TASK_ID" --force 2>/dev/null || true
  tmkill "claude-$TEST_TASK_ID" --force 2>/dev/null || true
}

@test "E2E Human: Complete workflow - create, validate, cleanup" {
  # 1. Create worktree
  run wtnew "$TEST_TASK_ID" claude main
  [ "$status" -eq 0 ]
  [[ "$output" == *"Created worktree"* ]]

  # 2. Create session
  run tmnew "$TEST_TASK_ID" claude
  [ "$status" -eq 0 ]
  [[ "$output" == *"Created session"* ]]

  # 3. Validate worktree
  run wtvalidate "wt-claude-$TEST_TASK_ID"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Validation complete"* ]]

  # 4. List worktrees
  run wtlist claude "$TEST_TASK_ID"
  [ "$status" -eq 0 ]
  [[ "$output" == *"wt-claude-$TEST_TASK_ID"* ]]

  # 5. List sessions
  run tmlist
  [ "$status" -eq 0 ]
  [[ "$output" == *"claude-$TEST_TASK_ID"* ]]

  # 6. Cleanup
  run wtrm "wt-claude-$TEST_TASK_ID" --force
  [ "$status" -eq 0 ]
  [[ "$output" == *"Removed"* ]]

  run tmkill "claude-$TEST_TASK_ID" --force
  [ "$status" -eq 0 ]
  [[ "$output" == *"Killed"* ]]
}

@test "E2E Human: Naming conflict handling" {
  local conflict_task="${TEST_TASK_ID}-conflict"

  # 1. Create first worktree
  wtnew "$conflict_task" claude main || true

  # 2. Try to create duplicate - should auto-suffix
  run wtnew "$conflict_task" claude main
  [ "$status" -eq 0 ]
  [[ "$output" == *"conflict detected"* ]] || [[ "$output" == *"exists"* ]]

  # Cleanup
  wtrm "wt-claude-$conflict_task" --force 2>/dev/null || true
  tmkill "claude-$conflict_task" --force 2>/dev/null || true
}

@test "E2E Human: Session recovery workflow" {
  local recovery_task="${TEST_TASK_ID}-recovery"

  # 1. Create environment
  wtnew "$recovery_task" claude main || true
  tmnew "$recovery_task" claude || true

  # 2. Kill session (simulate loss)
  tmkill "claude-$recovery_task" --force || true

  # 3. Recover session
  run wtrecover --task-id "$recovery_task"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Recovery complete"* ]]

  # Cleanup
  wtrm "wt-claude-$recovery_task" --force 2>/dev/null || true
  tmkill "claude-$recovery_task" --force 2>/dev/null || true
}

@test "E2E Human: Execution result query workflow" {
  local query_task="${TEST_TASK_ID}-query"

  # 1. Create worktree (writes execution result)
  wtnew "$query_task" claude main || true

  # 2. Query by task_id
  run query_by_task_id "$query_task"
  [ "$status" -eq 0 ]
  [[ "$output" == *"$query_task"* ]]

  # 3. Query by worktree
  run query_by_worktree "wt-claude-$query_task"
  [ "$status" -eq 0 ]
  [[ "$output" == *"$query_task"* ]]

  # Cleanup
  wtrm "wt-claude-$query_task" --force 2>/dev/null || true
}
