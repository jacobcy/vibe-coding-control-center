#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/roadmap_common.bash"

@test "roadmap list filters items and supports json output" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"
  jq '.items[0].linked_task_ids = ["2026-03-08-command-standard-rewrite"]' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap list --status current --linked --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq 'length')" -eq 1 ]
  [ "$(echo "$output" | jq -r '.[0].roadmap_item_id')" = "rm-1" ]
}

@test "roadmap show returns a single roadmap item as json" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap show rm-2 --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.roadmap_item_id')" = "rm-2" ]
  [ "$(echo "$output" | jq -r '.status')" = "p0" ]
  [ "$(echo "$output" | jq -r '.title')" = "Beta" ]
}