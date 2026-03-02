#!/usr/bin/env bats
# Tests for V3 Execution Plane - Tmux Capabilities

load test_utils

setup() {
  # Source the tmux functions
  source config/aliases/tmux.sh
}

@test "validate tmux session naming - valid format" {
  run _validate_tmux_session_name "claude-add-user-auth"
  [ "$status" -eq 0 ]
}

@test "validate tmux session naming - missing parts" {
  run _validate_tmux_session_name "claude"
  [ "$status" -eq 1 ]
  [[ "$output" == *"at least 2 parts"* ]]
}

@test "validate tmux session naming - empty name" {
  run _validate_tmux_session_name ""
  [ "$status" -eq 1 ]
  [[ "$output" == *"Empty name"* ]]
}

@test "validate tmux session naming - uppercase not allowed" {
  run _validate_tmux_session_name "Claude-Add-User"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Invalid naming format"* ]]
}

@test "parse session name - extract agent and task" {
  result=$(_parse_session_name "claude-add-user-auth")
  [ "$result" == "claude add-user-auth" ]
}

@test "parse session name - complex task" {
  result=$(_parse_session_name "opencode-fix-bug-123")
  [ "$result" == "opencode fix-bug-123" ]
}

@test "parse session name - simple" {
  result=$(_parse_session_name "claude-test")
  [ "$result" == "claude test" ]
}
