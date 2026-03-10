#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/flow_common.bash"

@test "flow contract: help states flow consumes existing execution records" {
  run vibe flow help

  [ "$status" -eq 0 ]
  [[ "$output" =~ "existing execution record" ]]
  [[ "$output" =~ "does not create planning objects" ]]
}

@test "flow contract: bind help requires an existing task" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_bind_usage
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "existing task" ]]
}

@test "flow contract: status json exposes execution summary without roadmap identity" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-claude-refactor"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[
  {"task_id":"task-main","title":"Main Task","status":"in_progress","next_step":"Gate 4","assigned_worktree":"wt-claude-refactor","spec_standard":"openspec","spec_ref":"openspec/changes/main","pr_ref":"#42"}
]}
JSON
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[
  {"worktree_name":"wt-claude-refactor","branch":"task/refactor","current_task":"task-main","tasks":["task-main"],"status":"active"}
]}
JSON

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="'"$VIBE_ROOT"'/lib"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 0
    }
    _flow_status --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.flows[0].current_task')" = "task-main" ]
  [ "$(echo "$output" | jq -r '.flows[0].spec_standard')" = "openspec" ]
  [ "$(echo "$output" | jq -r '.flows[0].spec_ref')" = "openspec/changes/main" ]
  [ "$(echo "$output" | jq -r '.flows[0].roadmap_item_id // "absent"')" = "absent" ]
  [ "$(echo "$output" | jq -r '.flows[0].github_project_item_id // "absent"')" = "absent" ]
}
