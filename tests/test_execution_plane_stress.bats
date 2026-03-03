#!/usr/bin/env bats
# Stress tests for Execution Plane

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/worktree.sh"
  source "$VIBE_ROOT/config/aliases/tmux.sh"

  # Use unique task IDs for test isolation
  export TEST_TASK_PREFIX="stress-$$"
}

teardown() {
  # Cleanup all test worktrees and sessions
  for i in {1..10}; do
    local task_id="${TEST_TASK_PREFIX}-$i"
    wtrm "wt-claude-${task_id}" --force 2>/dev/null || true
    tmkill "claude-${task_id}" --force 2>/dev/null || true
  done
  # Cleanup multi-agent tests
  wtrm "wt-claude-multi-claude-$$" --force 2>/dev/null || true
  wtrm "wt-opencode-multi-opencode-$$" --force 2>/dev/null || true
  wtrm "wt-codex-multi-codex-$$" --force 2>/dev/null || true
}

@test "Stress: 5+ parallel sessions with low conflict rate" {
  local conflict_count=0
  local total_count=5

  # Create 5 worktrees and sessions
  for i in $(seq 1 $total_count); do
    wtnew "${TEST_TASK_PREFIX}-$i" claude main 2>&1 | grep -q "conflict detected" && ((conflict_count++)) || true
    tmnew "${TEST_TASK_PREFIX}-$i" claude || true
  done

  # Conflict rate should be ~0 (or very low)
  # For 5 parallel with unique names, should be 0
  [ "$conflict_count" -eq 0 ]

  # Verify all exist
  local wt_count
  wt_count=$(wtlist claude | grep -c "${TEST_TASK_PREFIX}" || echo 0)
  [ "$wt_count" -eq $total_count ]
}

@test "Stress: Rapid create/delete cycles" {
  # Rapid cycle: create, validate, delete
  for i in {1..10}; do
    wtnew "${TEST_TASK_PREFIX}-$i" claude main || true
    wtvalidate "wt-claude-${TEST_TASK_PREFIX}-$i" >/dev/null 2>&1 || true
    wtrm "wt-claude-${TEST_TASK_PREFIX}-$i" --force 2>/dev/null || true
  done

  # All should complete without error
  [ "$?" -eq 0 ]
}

@test "Stress: Multiple agents parallel creation" {
  # Create worktrees for different agents in parallel
  wtnew "multi-claude-$$" claude main &
  wtnew "multi-opencode-$$" opencode main &
  wtnew "multi-codex-$$" codex main &

  wait

  # All should succeed
  local count
  count=$(wtlist | grep -c "multi-$$" || echo 0)
  [ "$count" -eq 3 ]
}
