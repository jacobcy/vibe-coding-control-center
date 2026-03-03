#!/usr/bin/env bats
# Tests for session recovery after tmux server restart

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/session-recovery.sh
  source "$VIBE_ROOT/config/aliases/execution-contract.sh
  source "$VIBE_ROOT/config/aliases/worktree.sh
  source "$VIBE_ROOT/config/aliases/tmux.sh
}

@test "Recovery: Session lost, worktree exists" {
  # Setup
  wtnew recovery-lost claude main || true
  tmnew recovery-lost claude || true

  # Kill session
  tmkill claude-recovery-lost --force || true

  # Recovery should recreate session
  run wtrecover --task-id recovery-lost
  [ "$status" -eq 0 ]
  [[ "$output" == *"Session recreated"* ]]
  [[ "$output" == *"Recovery complete"* ]]

  # Cleanup
  wtrm wt-claude-recovery-lost --force || true
  tmkill claude-recovery-lost --force || true
}

@test "Recovery: Both session and worktree lost" {
  # Setup and complete cleanup
  wtnew recovery-both-lost claude main || true
  tmnew recovery-both-lost claude || true
  wtrm wt-claude-recovery-both-lost --force || true
  tmkill claude-recovery-both-lost --force || true

  # Recovery should fail with instructions
  run wtrecover --task-id recovery-both-lost
  [ "$status" -eq 1 ]
  [[ "$output" == *"Worktree not found"* ]]
}

@test "Recovery: By worktree hint" {
  # Setup
  wtnew recovery-worktree claude main || true
  tmnew recovery-worktree claude || true

  # Recovery by worktree
  run wtrecover --worktree wt-claude-recovery-worktree
  [ "$status" -eq 0 ]
  [[ "$output" == *"Recovery complete"* ]]

  # Cleanup
  wtrm wt-claude-recovery-worktree --force || true
  tmkill claude-recovery-worktree --force || true
}

@test "Recovery: By session hint" {
  # Setup
  wtnew recovery-session claude main || true
  tmnew recovery-session claude || true

  # Recovery by session
  run wtrecover --session claude-recovery-session
  [ "$status" -eq 0 ]

  # Cleanup
  wtrm wt-claude-recovery-session --force || true
  tmkill claude-recovery-session --force || true
}

@test "Recovery: History logging" {
  # Setup
  wtnew recovery-history claude main || true

  # Recovery
  wtrecover --task-id recovery-history || true

  # Check history log
  run wtrecover-history recovery-history
  [ "$status" -eq 0 ]
  [[ "$output" == *"recovery-history"* ]]

  # Cleanup
  wtrm wt-claude-recovery-history --force || true
}
