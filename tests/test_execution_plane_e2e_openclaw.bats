#!/usr/bin/env bats
# End-to-end tests for Execution Plane - OpenClaw Mode

load test_utils

setup() {
  setup_test_env
  source skills/execution-plane/wrappers.sh
  export EXECUTOR=openclaw
}

@test "E2E OpenClaw: Complete automated workflow" {
  # 1. Prepare environment
  run skill_prepare_environment auto-task openclaw main
  [ "$status" -eq 0 ]
  [[ "$output" == *"Environment ready"* ]]
  [[ "$output" == *"OpenClaw Mode"* ]]

  # 2. Query execution state
  run skill_query_task auto-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"auto-task"* ]]
  [[ "$output" == *"openclaw"* ]]

  # 3. Validate worktree
  run skill_wtvalidate wt-openclaw-auto-task
  [ "$status" -eq 0 ]

  # 4. List worktrees (filtered)
  run skill_wtlist openclaw
  [ "$status" -eq 0 ]
  [[ "$output" == *"wt-openclaw-auto-task"* ]]

  # 5. Cleanup
  run skill_cleanup_environment auto-task openclaw
  [ "$status" -eq 0 ]
  [[ "$output" == *"Environment cleaned up"* ]]
}

@test "E2E OpenClaw: Executor mode persistence" {
  export EXECUTOR=openclaw

  # Create worktree
  skill_wtnew executor-test openclaw main || true

  # Query execution result
  result=$(query_by_task_id executor-test 2>/dev/null || echo "{}")

  # Verify executor field
  executor=$(echo "$result" | jq -r '.executor' 2>/dev/null)
  [ "$executor" == "openclaw" ]

  # Cleanup
  skill_cleanup_environment executor-test openclaw || true
}

@test "E2E OpenClaw: Batch operations" {
  # Create multiple environments
  skill_prepare_environment batch-1 openclaw main || true
  skill_prepare_environment batch-2 openclaw main || true
  skill_prepare_environment batch-3 openclaw main || true

  # List all openclaw worktrees
  result=$(skill_wtlist openclaw 2>&1)

  # Should contain all three
  [[ "$result" == *"batch-1"* ]]
  [[ "$result" == *"batch-2"* ]]
  [[ "$result" == *"batch-3"* ]]

  # Cleanup all
  skill_cleanup_environment batch-1 openclaw || true
  skill_cleanup_environment batch-2 openclaw || true
  skill_cleanup_environment batch-3 openclaw || true
}

@test "E2E OpenClaw: Recovery with auto-retry" {
  # Create environment
  skill_prepare_environment recovery-test openclaw main || true

  # Kill session (simulate loss)
  skill_tmkill openclaw-recovery-test || true

  # Attempt recovery (should auto-retry)
  run skill_wtrecover task-id recovery-test
  [ "$status" -eq 0 ]
  [[ "$output" == *"Recovery complete"* ]]

  # Cleanup
  skill_cleanup_environment recovery-test openclaw || true
}
