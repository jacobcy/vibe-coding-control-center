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

@test "roadmap item with no dependencies is ready" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap show rm-1 --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.dependency_status.ready')" = "true" ]
  [ "$(echo "$output" | jq -r '.dependency_status.blocked')" = "false" ]
  [ "$(echo "$output" | jq '.dependency_status.blockers | length')" -eq 0 ]
}

@test "roadmap item with unmerged dependency is blocked" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"

  # rm-2 depends on rm-1, but rm-1 has no merged PR
  jq '.items[1].depends_on_item_ids = ["rm-1"]' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap show rm-2 --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.dependency_status.ready')" = "false" ]
  [ "$(echo "$output" | jq -r '.dependency_status.blocked')" = "true" ]
  [ "$(echo "$output" | jq '.dependency_status.blockers | length')" -eq 1 ]
  [ "$(echo "$output" | jq -r '.dependency_status.blockers[0].roadmap_item_id')" = "rm-1" ]
  [ "$(echo "$output" | jq -r '.dependency_status.blockers[0].reason')" = "missing_pr_ref" ]
}

@test "roadmap item with merged dependency is ready" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"

  # rm-2 depends on rm-1, and rm-1 has a merged PR
  jq '.items[1].depends_on_item_ids = ["rm-1"]' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  # Add task with merged PR for rm-1
  jq '.tasks = [{"task_id":"task-1","roadmap_item_ids":["rm-1"],"pr_ref":"#123","pr_status":"merged","status":"completed"}]' "$fixture/vibe/registry.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/registry.json"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap show rm-2 --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.dependency_status.ready')" = "true" ]
  [ "$(echo "$output" | jq -r '.dependency_status.blocked')" = "false" ]
  [ "$(echo "$output" | jq '.dependency_status.blockers | length')" -eq 0 ]
}

@test "blocker distinguishes missing_pr_ref from pr_not_merged" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"

  # rm-2 depends on rm-1, and rm-1 has a PR but it's not merged
  jq '.items[1].depends_on_item_ids = ["rm-1"]' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  # Add task with open PR for rm-1
  jq '.tasks = [{"task_id":"task-1","roadmap_item_ids":["rm-1"],"pr_ref":"#123","pr_status":"open","status":"in_progress"}]' "$fixture/vibe/registry.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/registry.json"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap show rm-2 --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.dependency_status.blocked')" = "true" ]
  [ "$(echo "$output" | jq '.dependency_status.blockers | length')" -eq 1 ]
  [ "$(echo "$output" | jq -r '.dependency_status.blockers[0].roadmap_item_id')" = "rm-1" ]
  [ "$(echo "$output" | jq -r '.dependency_status.blockers[0].reason')" = "pr_not_merged" ]
}