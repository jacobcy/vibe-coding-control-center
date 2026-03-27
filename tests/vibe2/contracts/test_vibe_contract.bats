#!/usr/bin/env bats

setup() {
  export PATH="$BATS_TEST_DIRNAME/../../../bin:$PATH"
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

@test "bin/vibe is executable" {
  [ -x "$BATS_TEST_DIRNAME/../../../bin/vibe" ]
}

@test "vibe help outputs Usage" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "vibe without args returns help info" {
  run vibe
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "vibe help mentions issue to task to flow onboarding" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "repo issue / roadmap item" ]]
}

@test "vibe help mentions task command" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "execution record 生命周期管理" ]]
}

@test "vibe help mentions task add update remove" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "list, add, update, remove" ]]
}

@test "vibe help does not advertise unsupported skills audit subcommand" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "sync, check, audit" ]]
}

@test "invalid subcommand returns error" {
  run vibe invalidcommand
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unknown command" ]]
}

@test "VIBE_ROOT is set correctly in script" {
  local expected_root
  expected_root="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  run zsh -c "unset VIBE_ROOT VIBE_LIB; source $BATS_TEST_DIRNAME/../../../bin/vibe >/dev/null && echo \$VIBE_ROOT"
  [ "$status" -eq 0 ]
  [ "$output" = "$expected_root" ]
}

@test "vibe version outputs version info" {
  run vibe version
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe" ]]
}

@test "vibe task help lists subcommands" {
  run vibe task --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
  [[ "$output" =~ "vibe task" ]]
  [[ "$output" =~ "add" ]]
  [[ "$output" =~ "show" ]]
  [[ "$output" =~ "update" ]]
  [[ "$output" =~ "remove" ]]
  [[ "$output" =~ "audit" ]]
  [[ ! "$output" =~ "sync" ]]
}

@test "vibe flow bind help mentions task id" {
  run vibe flow bind --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe flow bind <task-id>" ]]
}

@test "vibe roadmap help is available" {
  run vibe roadmap help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe Roadmap" ]]
  [[ "$output" =~ "classify" ]]
}

@test "vibe alias load points to the new runtime loader" {
  run vibe alias --load
  [ "$status" -eq 0 ]
  [[ -f "$output" ]]
  [[ "$output" =~ "lib/alias/loader.sh" ]]
  [[ ! "$output" =~ "config/aliases.sh" ]]
}