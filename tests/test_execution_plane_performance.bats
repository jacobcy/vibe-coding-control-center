#!/usr/bin/env bats
# Performance tests for Execution Plane

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/session-recovery.sh"
  source "$VIBE_ROOT/config/aliases/worktree.sh"
  source "$VIBE_ROOT/config/aliases/tmux.sh"

  # Use unique task IDs for test isolation
  export TEST_TASK_ID="perf-$$"
}

teardown() {
  # Cleanup test artifacts
  wtrm "wt-claude-$TEST_TASK_ID" --force 2>/dev/null || true
  tmkill "claude-$TEST_TASK_ID" --force 2>/dev/null || true
}

@test "Performance: Recovery time < 30 seconds" {
  # Setup
  wtnew "$TEST_TASK_ID" claude main || true
  tmnew "$TEST_TASK_ID" claude || true

  # Kill session
  tmkill "claude-$TEST_TASK_ID" --force || true

  # Measure recovery time
  local start end duration
  start=$(date +%s)
  wtrecover --task-id "$TEST_TASK_ID" || true
  end=$(date +%s)
  duration=$((end - start))

  [ "$duration" -lt 30 ]
  [[ "$output" == *"Recovery complete"* ]]
}

@test "Performance: Worktree creation < 5 seconds" {
  # Setup
  local start end duration
  start=$(date +%s)
  wtnew "$TEST_TASK_ID" claude main || true
  end=$(date +%s)
  duration=$((end - start))

  [ "$duration" -lt 5 ]
  [[ "$output" == *"Created worktree"* ]]
}

@test "Performance: Session creation < 2 seconds" {
  # Setup
  local start end duration
  start=$(date +%s)
  tmnew "$TEST_TASK_ID" claude || true
  end=$(date +%s)
  duration=$((end - start))

  [ "$duration" -lt 2 ]
  [[ "$output" == *"Created session"* ]]
}

@test "Performance: Query by task_id < 1 second" {
  # Setup
  wtnew "$TEST_TASK_ID" claude main || true

  # Measure query time
  local start end duration
  start=$(date +%s)
  query_by_task_id "$TEST_TASK_ID" || true
  end=$(date +%s)
  duration=$((end - start))

  [ "$duration" -lt 1 ]
  [[ "$output" == *"$TEST_TASK_ID"* ]]
}
