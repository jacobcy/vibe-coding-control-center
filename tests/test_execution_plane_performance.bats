#!/usr/bin/env bats
# Performance tests for Execution Plane

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/session-recovery.sh
  source "$VIBE_ROOT/config/aliases/worktree.sh"
  source "$VIBE_ROOT/config/aliases/tmux.sh"
}

@test "Performance: Recovery time < 30 seconds" {
  # Setup
  wtnew perf-recovery claude main || true
  tmnew perf-recovery claude || true

  # Kill session
  tmkill claude-perf-recovery --force || true

  # Measure recovery time
  local start end duration
  start=$(date +%s)

  wtrecover --task-id perf-recovery

  end=$(date +%s)
  duration=$((end - start))

  # Should be < 30 seconds
  [ "$duration" -lt 30 ]

  # Cleanup
  wtrm wt-claude-perf-recovery --force || true
  tmkill claude-perf-recovery --force || true
}

@test "Performance: Worktree creation < 5 seconds" {
  local start end duration
  start=$(date +%s)

  wtnew perf-creation claude main

  end=$(date +%s)
  duration=$((end - start))

  # Should be < 5 seconds
  [ "$duration" -lt 5 ]

  # Cleanup
  wtrm wt-claude-perf-creation --force || true
}

@test "Performance: Session creation < 2 seconds" {
  local start end duration
  start=$(date +%s)

  tmnew perf-session claude

  end=$(date +%s)
  duration=$((end - start))

  # Should be < 2 seconds
  [ "$duration" -lt 2 ]

  # Cleanup
  tmkill claude-perf-session --force || true
}

@test "Performance: Query by task_id < 1 second" {
  source "$VIBE_ROOT/config/aliases/execution-contract.sh"

  # Setup
  wtnew perf-query claude main || true

  local start end duration
  start=$(date +%s)

  query_by_task_id perf-query >/dev/null 2>&1

  end=$(date +%s)
  duration=$((end - start))

  # Should be < 1 second
  [ "$duration" -lt 1 ]

  # Cleanup
  wtrm wt-claude-perf-query --force || true
}

@test "Performance: Worktree validation < 5 seconds" {
  # Setup
  wtnew perf-validate claude main || true

  local start end duration
  start=$(date +%s)

  wtvalidate wt-claude-perf-validate

  end=$(date +%s)
  duration=$((end - start))

  # Should be < 5 seconds
  [ "$duration" -lt 5 ]

  # Cleanup
  wtrm wt-claude-perf-validate --force || true
}
