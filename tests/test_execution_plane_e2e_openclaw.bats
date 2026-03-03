#!/usr/bin/env bats
# End-to-end tests for Execution Plane - OpenClaw Mode

load test_utils

setup() {
  setup_test_env
  source skills/execution-plane/wrappers.sh

  # Use unique task ID for test isolation
  export TEST_TASK_ID="e2e-openclaw-$$"
}

teardown() {
  # Cleanup test artifacts
  [[ -n "$TEST_TASK_ID" ]] && {
    skill_cleanup_environment "$TEST_TASK_ID" openclaw 2>/dev/null || true
  }
}

@test "E2E OpenClaw: Complete automated workflow" {
  # 1. Prepare environment with unique ID
  run skill_prepare_environment "$TEST_TASK_ID" openclaw main
  [ "$status" -eq 0 ]
  [[ "$output" == *"Environment ready"* ]]
  [[ "$output" == *"OpenClaw Mode"* ]]

  # 2. Query execution state
  run skill_query_task "$TEST_TASK_ID"
  [ "$status" -eq 0 ]
  [[ "$output" == *"$TEST_TASK_ID"* ]]
  [[ "$output" == *"openclaw"* ]]

  # 3. Validate worktree
  run skill_wtvalidate "wt-openclaw-$TEST_TASK_ID"
  [ "$status" -eq 0 ]

  # 4. List worktrees (filtered)
  run skill_wtlist openclaw
  [ "$status" -eq 0 ]
}

@test "E2E OpenClaw: Executor mode persistence" {
  run skill_prepare_environment "${TEST_TASK_ID}-exec" openclaw main
  [ "$status" -eq 0 ]

  # Check executor is set
  run skill_query_task "${TEST_TASK_ID}-exec"
  [ "$status" -eq 0 ]
  [[ "$output" == *"openclaw"* ]]
}

@test "E2E OpenClaw: Batch operations" {
  # Create multiple environments
  for i in {1..3}; do
    run skill_prepare_environment "${TEST_TASK_ID}-batch-$i" openclaw main
    [ "$status" -eq 0 ]
  done

  # List all
  run skill_wtlist openclaw
  [ "$status" -eq 0 ]

  # Cleanup all
  for i in {1..3}; do
    skill_cleanup_environment "${TEST_TASK_ID}-batch-$i" openclaw 2>/dev/null || true
  done
}

@test "E2E OpenClaw: Recovery with auto-retry" {
  # Create environment
  run skill_prepare_environment "${TEST_TASK_ID}-recover" openclaw main
  [ "$status" -eq 0 ]

  # Kill session
  skill_tmkill "${TEST_TASK_ID}-recover" openclaw 2>/dev/null || true

  # Recovery should work
  run skill_wtrecover task-id "${TEST_TASK_ID}-recover"
  [ "$status" -eq 0 ]
}
