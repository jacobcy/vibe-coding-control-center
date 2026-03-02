#!/usr/bin/env bats

setup() {
  export PATH="$BATS_TEST_DIRNAME/../bin:$PATH"
}

@test "1. bin/vibe is executable" {
  [ -x "$BATS_TEST_DIRNAME/../bin/vibe" ]
}

@test "2. bin/vibe check returns success without errors" {
  run vibe check
  [ "$status" -eq 0 ]
}

@test "3. vibe help outputs Usage" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "4. vibe without args returns help info" {
  run vibe
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "4.1 vibe help mentions /vibe-new onboarding" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "/vibe-new <feature>" ]]
}

@test "4.2 vibe help mentions task command" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "查看跨 worktree 的任务总览" ]]
}

@test "4.3 vibe help does not advertise unsupported skills audit subcommand" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "sync, check, audit" ]]
}

@test "5. invalid subcommand returns error" {
  run vibe invalidcommand
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unknown command" ]]
}

@test "6. VIBE_ROOT is set correctly in script" {
  run zsh -c "source $BATS_TEST_DIRNAME/../bin/vibe && echo \$VIBE_ROOT"
  [ "$status" -eq 0 ]
  [ -n "$output" ]
}

@test "7. vibe version outputs version info" {
  run vibe version
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe" ]]
}
