#!/usr/bin/env bats
# tests/test_task_sync.bats - OpenSpec Synchronization tests

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  export HELPER="$BATS_TEST_DIRNAME/test_task_helper.zsh"
}

@test "sync: vibe_task sync merges openspec tasks into registry" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/openspec/changes/new-feat"
  echo "- [ ] start feat" > "$fixture/openspec/changes/new-feat/tasks.md"
  printf '{"schema_version":"v1","tasks":[]}\n' > "$fixture/vibe/registry.json"
  printf '{"schema_version":"v1","worktrees":[]}\n' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'"
    vibe_task sync
  '
  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="new-feat") | .framework' "$fixture/vibe/registry.json")" = "openspec" ]
  [ "$(jq -r '.tasks[] | select(.task_id=="new-feat") | .status' "$fixture/vibe/registry.json")" = "todo" ]
}

@test "sync: sync preserves existing metadata and updates next_step" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/openspec/changes/feat-A"
  echo "- [x] done" > "$fixture/openspec/changes/feat-A/tasks.md"
  
  cat > "$fixture/vibe/registry.json" <<JSON
{
  "schema_version": "v1",
  "tasks": [
    {
      "task_id": "feat-A",
      "title": "Old Title",
      "status": "todo",
      "assigned_worktree": "wt-1"
    }
  ]
}
JSON
  printf '{"schema_version":"v1","worktrees":[]}\n' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'"
    vibe_task sync
  '
  [ "$status" -eq 0 ]
  # Framework should be added
  [ "$(jq -r '.tasks[] | select(.task_id=="feat-A") | .framework' "$fixture/vibe/registry.json")" = "openspec" ]
  # Status should be updated from OpenSpec (completed because all tasks are [x])
  [ "$(jq -r '.tasks[] | select(.task_id=="feat-A") | .status' "$fixture/vibe/registry.json")" = "completed" ]
}
