#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/roadmap_common.bash"

@test "roadmap status reads roadmap.json instead of registry roadmap block" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd_no_tty "$fixture" '_vibe_roadmap_status'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Version Goal: Complete shared-state standardization" ]]
  [[ "$output" =~ "P0 (urgent):      1" ]]
  [[ "$output" =~ "Current:          1" ]]
  [[ ! "$output" =~ "Current Version:" ]]
  [[ ! "$output" =~ $'\033' ]]
}

@test "roadmap status supports json output" {
  local fixture
  local tmp
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"
  jq '.project_id = null | .items |= map(.github_project_item_id = null)' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap status --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.version_goal')" = "Complete shared-state standardization" ]
  [ "$(echo "$output" | jq -r '.counts.p0')" = "1" ]
  [ "$(echo "$output" | jq -r '.counts.current')" = "1" ]
  [ "$(echo "$output" | jq -r '.counts.deferred')" = "1" ]
  [ "$(echo "$output" | jq -r '.sync_check.recommended')" = "true" ]
  [ "$(echo "$output" | jq -r '.sync_check.missing_project_id')" = "1" ]
  [ "$(echo "$output" | jq -r '.sync_check.missing_github_project_item_id')" = "3" ]
  [ "$(echo "$output" | jq -r '.sync_check.recommended_command')" = "vibe roadmap sync --provider github --json" ]
}

@test "roadmap status text output recommends sync when official layer is incomplete" {
  local fixture
  local tmp
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"
  jq '.project_id = null | .items |= map(.github_project_item_id = null)' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  run_roadmap_fixture_cmd_no_tty "$fixture" '_vibe_roadmap_status'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Roadmap sync recommended" ]]
  [[ "$output" =~ "vibe roadmap sync --provider github --json" ]]
}

@test "roadmap status text uses clarified layer labels" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd_no_tty "$fixture" '_vibe_roadmap_status'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Roadmap Item Summary:" ]]
  [[ "$output" =~ "GitHub Project Mirror:" ]]
  [[ "$output" =~ "Local Execution Bridge:" ]]
}

@test "roadmap list text output avoids repeating id when title matches id" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"
  jq '.items = [{"roadmap_item_id":"gh-36","title":"gh-36","description":null,"status":"p0","source_type":"github","source_refs":[],"issue_refs":["gh-36"],"linked_task_ids":[],"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"}]' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  run_roadmap_fixture_cmd_no_tty "$fixture" 'vibe_roadmap list'

  [ "$status" -eq 0 ]
  [ "$output" = $'P0 (1)\n  gh-36' ]
  [[ ! "$output" =~ $'\033' ]]
}

@test "roadmap list text output groups items by status" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd_no_tty "$fixture" 'vibe_roadmap list'

  [ "$status" -eq 0 ]
  [ "$output" = $'P0 (1)\n  rm-2  Beta\n\nCurrent (1)\n  rm-1  Alpha\n\nDeferred (1)\n  rm-3  Gamma' ]
  [[ ! "$output" =~ $'\033' ]]
}

@test "roadmap list color output highlights grouped status headings" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" '_vibe_roadmap_supports_color() { return 0; }; vibe_roadmap list'

  [ "$status" -eq 0 ]
  [[ "$output" =~ $'\033' ]]
  [[ "$output" =~ "P0 (1)" ]]
  [[ "$output" =~ "Current (1)" ]]
}

@test "roadmap color support allows interactive stdin when stdout is not a tty" {
  run_roadmap_cmd '_vibe_roadmap_fd_is_tty() { [[ "$1" == "0" ]]; }; if _vibe_roadmap_supports_color; then echo yes; else echo no; fi'

  [ "$status" -eq 0 ]
  [ "$output" = "yes" ]
}

@test "roadmap show text output omits ansi escapes when stdout is not a tty" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd_no_tty "$fixture" 'vibe_roadmap show rm-2'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Roadmap Item: rm-2" ]]
  [[ "$output" =~ "Status:      p0" ]]
  [[ ! "$output" =~ $'\033' ]]
}
