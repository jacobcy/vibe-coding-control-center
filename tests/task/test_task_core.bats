#!/usr/bin/env bats
# tests/task/test_task_core.bats - Core routing and safety tests

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export HELPER="$BATS_TEST_DIRNAME/test_task_helper.zsh"
}

@test "core: vibe_task fails outside git repository" {
  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    git() { return 128; }
    vibe_task
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Not in a git repository" ]]
}

@test "core: vibe_task fails when registry.json is missing" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  echo '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"
  # Missing registry.json

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    vibe_die() { echo "$@"; exit 1; }
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task
  '
  [ "$status" -eq 1 ]
  echo "$output" | grep -F "Missing registry.json"
}

@test "core: vibe_task fails when current task is missing from registry" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[{"worktree_name":"wt-test-task","worktree_path":"/tmp/wt-test-task","branch":"refactor","current_task":"missing-task","status":"active","dirty":true}]}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"diff-task","title":"Diff Task","status":"done"}]}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    vibe_die() { echo "$@"; exit 1; }
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Task not found in registry: missing-task" ]]
}

@test "core: subcommands help prints usage" {
  run zsh -c 'source "'"$HELPER"'"; setup_task_env; vibe_task add --help'
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage: vibe task add" ]]

  run zsh -c 'source "'"$HELPER"'"; setup_task_env; vibe_task update --help'
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe Task Manager" ]]

  run zsh -c 'source "'"$HELPER"'"; setup_task_env; vibe_task remove --help'
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage: vibe task remove [--yes] <task-id>"* ]]
}

@test "core: unknown subcommand fails" {
  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    vibe_die() { echo "$@"; exit 1; }
    vibe_task unknown_cmd
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unknown task subcommand" ]]
}
