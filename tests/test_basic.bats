#!/usr/bin/env bats

@test "1. bin/vibe is executable" {
  [ -x "bin/vibe" ]
}

@test "2. bin/vibe check returns success without errors" {
  run bin/vibe check
  [ "$status" -eq 0 ]
}
