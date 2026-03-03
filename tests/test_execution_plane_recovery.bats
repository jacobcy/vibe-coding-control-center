#!/usr/bin/env bats
# Tests for session recovery after tmux server restart

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/session-recovery.sh"
  source "$VIBE_ROOT/config/aliases/execution-contract.sh"
  source "$VIBE_ROOT/config/aliases/worktree.sh"
  source "$VIBE_ROOT/config/aliases/tmux.sh"

  # Use unique task IDs for test isolation
  export TEST_TASK_ID="recovery-$$"
}

teardown() {
  # Cleanup test artifacts
  wtrm "wt-claude-$TEST_TASK_ID" --force 2>/dev/null || true
  tmkill "claude-$TEST_TASK_ID" --force 2>/dev/null || true
}

@test "Recovery: Session lost, worktree exists" {
  local task="${TEST_TASK_ID}-lost"

  # Setup
  wtnew "$task" claude main || true
  tmnew "$task" claude || true

  # Kill session
  tmkill "claude-$task" --force || true

  # Recovery should recreate session
  run wtrecover --task-id "$task"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Session recreated"* ]]
  [[ "$output" == *"Recovery complete"* ]]
}

@test "Recovery: Both session and worktree lost" {
  local task="${TEST_TASK_ID}-both"

  # Setup and complete cleanup
  wtnew "$task" claude main || true
  tmnew "$task" claude || true
  wtrm "wt-claude-$task" --force || true
  tmkill "claude-$task" --force || true

  # Recovery should fail with instructions
  run wtrecover --task-id "$task"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Worktree not found"* ]]
}

@test "Recovery: By worktree hint" {
  local task="${TEST_TASK_ID}-worktree"

  # Setup
  wtnew "$task" claude main || true
  tmnew "$task" claude || true

  # Recovery by worktree
  run wtrecover --worktree "wt-claude-$task"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Recovery complete"* ]]
}

@test "Recovery: By session hint" {
  local task="${TEST_TASK_ID}-session"

  # Setup
  wtnew "$task" claude main || true
  tmnew "$task" claude || true

  # Recovery by session
  run wtrecover --session "claude-$task"
  [ "$status" -eq 0 ]
}

@test "Recovery: History logging" {
  local task="${TEST_TASK_ID}-history"

  # Setup
  wtnew "$task" claude main || true

  # Recovery
  wtrecover --task-id "$task" || true

  # Check history log
  run wtrecover-history "$task"
  [ "$status" -eq 0 ]
  [[ "$output" == *"$task"* ]]
}
