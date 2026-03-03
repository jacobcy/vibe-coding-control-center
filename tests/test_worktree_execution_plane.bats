#!/usr/bin/env bats
# Tests for V3 Execution Plane - Worktree Capabilities

load test_utils

setup() {
  setup_test_env
  # Source the worktree functions
  source "$VIBE_ROOT/config/aliases/worktree.sh"
}

@test "validate worktree naming - valid format" {
  run _validate_worktree_name "wt-claude-add-user-auth"
  [ "$status" -eq 0 ]
}

@test "validate worktree naming - missing prefix" {
  run _validate_worktree_name "claude-add-user-auth"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Invalid naming format"* ]]
}

@test "validate worktree naming - too short" {
  run _validate_worktree_name "wt-claude"
  [ "$status" -eq 1 ]
  [[ "$output" == *"at least 3 parts"* ]]
}

@test "validate worktree naming - empty name" {
  run _validate_worktree_name ""
  [ "$status" -eq 1 ]
  [[ "$output" == *"Empty name"* ]]
}

@test "validate worktree naming - uppercase not allowed" {
  run _validate_worktree_name "wt-Claude-Add-User"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Invalid naming format"* ]]
}

@test "generate conflict suffix - 4 characters" {
  suffix=$(_generate_conflict_suffix)
  [ ${#suffix} -eq 4 ]
}

@test "generate conflict suffix - alphanumeric" {
  suffix=$(_generate_conflict_suffix)
  [[ "$suffix" =~ ^[a-f0-9]{4}$ ]]
}

@test "generate conflict suffix - unique values" {
  suffix1=$(_generate_conflict_suffix)
  sleep 1
  suffix2=$(_generate_conflict_suffix)
  # Highly unlikely to be the same
  [ "$suffix1" != "$suffix2" ]
}
