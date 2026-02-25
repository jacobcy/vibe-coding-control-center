#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$BATS_TEST_DIRNAME/.."
  # Source the utils module
  source "$VIBE_ROOT/lib/config.sh"
  source "$VIBE_ROOT/lib/utils.sh"
}

@test "1. log_info outputs info message" {
  run log_info "test message"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "ℹ" ]] || [[ "$output" =~ "INFO" ]]
  [[ "$output" =~ "test message" ]]
}

@test "2. log_error outputs error message" {
  run zsh -c "source \"$VIBE_ROOT/lib/config.sh\" && source \"$VIBE_ROOT/lib/utils.sh\" && log_error \"test error\""
  [ "$status" -eq 0 ]
  [[ "$output" =~ "✗" ]] || [[ "$output" =~ "ERROR" ]]
  [[ "$output" =~ "test error" ]]
}

@test "3. log_success outputs success message" {
  run log_success "test success"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "★" ]] || [[ "$output" =~ "✓" ]] || [[ "$output" =~ "SUCCESS" ]]
  [[ "$output" =~ "test success" ]]
}

@test "4. vibe_has returns success for existing command" {
  run zsh -c "source \"$VIBE_ROOT/lib/config.sh\" && source \"$VIBE_ROOT/lib/utils.sh\" && vibe_has ls"
  [ "$status" -eq 0 ]
}

@test "5. vibe_has returns failure for non-existent command" {
  run zsh -c "source \"$VIBE_ROOT/lib/config.sh\" && source \"$VIBE_ROOT/lib/utils.sh\" && vibe_has a_command_that_does_not_exist_xyz123"
  [ "$status" -eq 1 ]
}

@test "6. helper functions required by aliases exist" {
  run zsh -c "source \"$VIBE_ROOT/lib/config.sh\" && source \"$VIBE_ROOT/lib/utils.sh\" && type vibe_require vibe_find_cmd vibe_die"
  [ "$status" -eq 0 ]
}

@test "7. vibe_require fails when command is missing" {
  run zsh -c "source \"$VIBE_ROOT/lib/config.sh\" && source \"$VIBE_ROOT/lib/utils.sh\" && vibe_require definitely_missing_command_xyz"
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Missing commands" ]]
}
