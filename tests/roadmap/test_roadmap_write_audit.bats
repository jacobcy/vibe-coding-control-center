#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/roadmap_common.bash"

@test "roadmap assign writes version_goal to roadmap.json root" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap assign "Ship roadmap split"'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Version goal set to: Ship roadmap split" ]]
  [[ "$output" =~ "planning window" ]]
  [ "$(jq -r '.version_goal' "$fixture/vibe/roadmap.json")" = "Ship roadmap split" ]
}

@test "roadmap classify updates an existing roadmap item in roadmap.json" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap classify rm-1 --status next'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Roadmap item rm-1 (Alpha) classified as: next" ]]
  [ "$(jq -r '.items[] | select(.roadmap_item_id=="rm-1") | .status' "$fixture/vibe/roadmap.json")" = "next" ]
}

@test "roadmap classify fails when roadmap item does not already exist" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap classify rm-new --status next'

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Error: Roadmap item 'rm-new' not found" ]]
  [ "$(jq '[.items[] | select(.roadmap_item_id=="rm-new")] | length' "$fixture/vibe/roadmap.json")" = "0" ]
}

@test "roadmap version set-goal writes version_goal to roadmap.json" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap version set-goal "Ship roadmap split"'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Version goal set to: Ship roadmap split" ]]
  [ "$(jq -r '.version_goal' "$fixture/vibe/roadmap.json")" = "Ship roadmap split" ]
}

@test "roadmap version clear-goal clears version_goal in roadmap.json" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap version clear-goal'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Version goal cleared." ]]
  [[ "$output" =~ "Next:" ]]
  [ "$(jq -r '.version_goal' "$fixture/vibe/roadmap.json")" = "null" ]
}

@test "roadmap add creates a local roadmap item in roadmap.json" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" '_vibe_roadmap_create_github_draft_issue() { echo "PVTI_created"; return 0; }; vibe_roadmap add "Local roadmap item"'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Roadmap item added:" ]]
  [[ "$output" =~ "Local roadmap item" ]]
  [ "$(jq -r '.items[] | select(.title=="Local roadmap item") | .source_type' "$fixture/vibe/roadmap.json")" = "local" ]
}

@test "roadmap add --help shows usage without creating a roadmap item" {
  local fixture
  local initial_count
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  initial_count="$(jq '.items | length' "$fixture/vibe/roadmap.json")"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap add --help'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe Roadmap - 智能调度器" ]]
  [ "$(jq '.items | length' "$fixture/vibe/roadmap.json")" = "$initial_count" ]
}

@test "roadmap init creates missing shared-state skeleton without syncing or task recovery" {
  local fixture
  fixture="$(mktemp -d)"
  make_empty_shared_state_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'export GITHUB_PROJECT_ID="PVT_test_roadmap_init"; vibe_roadmap init'

  [ "$status" -eq 0 ]
  [ -d "$fixture/vibe/tasks" ]
  [ -d "$fixture/vibe/pending-tasks" ]
  [ -f "$fixture/vibe/roadmap.json" ]
  [ -f "$fixture/vibe/registry.json" ]
  [ -f "$fixture/vibe/worktrees.json" ]
  [ "$(jq -r '.schema_version' "$fixture/vibe/roadmap.json")" = "v2" ]
  [ "$(jq -r '.project_id // "null"' "$fixture/vibe/roadmap.json")" = "PVT_test_roadmap_init" ]
  [ "$(jq -r '.schema_version' "$fixture/vibe/registry.json")" = "v2" ]
  [ "$(jq '.tasks | length' "$fixture/vibe/registry.json")" = "0" ]
  [ "$(jq -r '.schema_version' "$fixture/vibe/worktrees.json")" = "v2" ]
  [ "$(jq '.worktrees | length' "$fixture/vibe/worktrees.json")" = "0" ]
  [[ ! -e "$fixture/vibe/tasks/task-old" ]]
}

@test "roadmap init --force replaces corrupted shared-state files with empty skeleton data" {
  local fixture
  fixture="$(mktemp -d)"
  make_empty_shared_state_fixture "$fixture"
  mkdir -p "$fixture/vibe/tasks/task-old" "$fixture/vibe/pending-tasks"
  printf '%s\n' 'not-json' > "$fixture/vibe/roadmap.json"
  printf '%s\n' '{"schema_version":"v2","tasks":[{"task_id":"task-old"}]}' > "$fixture/vibe/registry.json"
  printf '%s\n' '{"schema_version":"v2","worktrees":[{"worktree_name":"wt-old"}]}' > "$fixture/vibe/worktrees.json"

  run_roadmap_fixture_cmd "$fixture" 'export GITHUB_PROJECT_ID="PVT_test_roadmap_force"; vibe_roadmap init --force'

  [ "$status" -eq 0 ]
  [ "$(jq -r '.schema_version' "$fixture/vibe/roadmap.json")" = "v2" ]
  [ "$(jq -r '.project_id // "null"' "$fixture/vibe/roadmap.json")" = "PVT_test_roadmap_force" ]
  [ "$(jq '.items | length' "$fixture/vibe/roadmap.json")" = "0" ]
  [ "$(jq '.tasks | length' "$fixture/vibe/registry.json")" = "0" ]
  [ "$(jq '.worktrees | length' "$fixture/vibe/worktrees.json")" = "0" ]
  [[ ! -e "$fixture/vibe/tasks/task-old" ]]
}

@test "roadmap audit returns json summary when checks pass" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"
  jq '.items |= map(.linked_task_ids = ["2026-03-08-command-standard-rewrite"])' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap audit --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.ok')" = "true" ]
  [ "$(echo "$output" | jq -r '.checks.version_goal.present')" = "true" ]
}

@test "roadmap audit defaults do not fail on unlinked items" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap audit --json'

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.ok')" = "true" ]
  [ "$(echo "$output" | jq -r '.checks.links.enabled')" = "false" ]
}

@test "roadmap audit fails when status is invalid" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"
  jq '.items[1].status = "broken"' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap audit --check-status --json'

  [ "$status" -eq 1 ]
  [ "$(echo "$output" | jq -r '.ok')" = "false" ]
  [ "$(echo "$output" | jq -r '.checks.status.invalid_item_ids[0]')" = "rm-2" ]
}
