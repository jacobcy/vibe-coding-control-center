#!/usr/bin/env bats
# tests/task/test_task_sync.bats - Task audit synchronization tests

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export HELPER="$BATS_TEST_DIRNAME/test_task_helper.zsh"
}

@test "audit: check-openspec reports unsynced changes" {
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
    vibe_task audit --check-openspec
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "new-feat" ]]
}

@test "audit: check-openspec works from subdirectory" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/subdir" "$fixture/openspec/changes/feat-A"
  echo "- [x] done" > "$fixture/openspec/changes/feat-A/tasks.md"
  printf '{"schema_version":"v1","tasks":[]}\n' > "$fixture/vibe/registry.json"
  printf '{"schema_version":"v1","worktrees":[]}\n' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'/subdir"
    vibe_task audit --check-openspec
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "feat-A" ]]
}
