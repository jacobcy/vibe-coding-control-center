#!/usr/bin/env bats
# End-to-end tests for Execution Plane - Human Mode

load test_utils

setup() {
  source config/aliases/worktree.sh
  source config/aliases/tmux.sh
  source config/aliases/execution-contract.sh
  source config/aliases/session-recovery.sh

  # Mock git commands for testing
  export VIBE_GIT_MOCK=1
}

@test "E2E Human: Complete workflow - create, validate, cleanup" {
  # 1. Create worktree
  run wtnew test-feature claude main
  [ "$status" -eq 0 ]
  [[ "$output" == *"Created worktree"* ]]

  # 2. Create session
  run tmnew test-feature claude
  [ "$status" -eq 0 ]
  [[ "$output" == *"Created session"* ]]

  # 3. Validate worktree
  run wtvalidate wt-claude-test-feature
  [ "$status" -eq 0 ]
  [[ "$output" == *"Validation complete"* ]]

  # 4. List worktrees
  run wtlist claude test-feature
  [ "$status" -eq 0 ]
  [[ "$output" == *"wt-claude-test-feature"* ]]

  # 5. List sessions
  run tmlist
  [ "$status" -eq 0 ]
  [[ "$output" == *"claude-test-feature"* ]]

  # 6. Cleanup
  run wtrm wt-claude-test-feature --force
  [ "$status" -eq 0 ]
  [[ "$output" == *"Removed"* ]]

  run tmkill claude-test-feature --force
  [ "$status" -eq 0 ]
  [[ "$output" == *"Killed"* ]]
}

@test "E2E Human: Naming conflict handling" {
  # 1. Create first worktree
  wtnew conflict-test claude main || true

  # 2. Try to create duplicate - should auto-suffix
  run wtnew conflict-test claude main
  [ "$status" -eq 0 ]
  [[ "$output" == *"conflict detected"* ]] || [[ "$output" == *"exists"* ]]

  # Cleanup
  wtrm wt-claude-conflict-test --force || true
  tmkill claude-conflict-test --force || true
}

@test "E2E Human: Session recovery workflow" {
  # 1. Create environment
  wtnew recovery-test claude main || true
  tmnew recovery-test claude || true

  # 2. Kill session (simulate loss)
  tmkill claude-recovery-test --force || true

  # 3. Recover session
  run wtrecover --task-id recovery-test
  [ "$status" -eq 0 ]
  [[ "$output" == *"Recovery complete"* ]]

  # Cleanup
  wtrm wt-claude-recovery-test --force || true
  tmkill claude-recovery-test --force || true
}

@test "E2E Human: Execution result query workflow" {
  # 1. Create worktree (writes execution result)
  wtnew query-test claude main || true

  # 2. Query by task_id
  run query_by_task_id query-test
  [ "$status" -eq 0 ]
  [[ "$output" == *"query-test"* ]]

  # 3. Query by worktree
  run query_by_worktree wt-claude-query-test
  [ "$status" -eq 0 ]
  [[ "$output" == *"query-test"* ]]

  # Cleanup
  wtrm wt-claude-query-test --force || true
}
