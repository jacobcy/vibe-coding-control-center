#!/usr/bin/env bats
# tests/test_task_ops.bats - Task Mutation Operations (Add, Update, Remove)

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  export HELPER="$BATS_TEST_DIRNAME/test_task_helper.zsh"
}

@test "ops: vibe_task add creates registry entry and source file" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '{"schema_version":"v1","tasks":[]}\n' > "$fixture/vibe/registry.json"
  printf '{"schema_version":"v1","worktrees":[]}\n' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task add "New Task Title" --id 2026-03-04-new-task
  '
  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-04-new-task") | .title' "$fixture/vibe/registry.json")" = "New Task Title" ]
  [ -f "$fixture/vibe/tasks/2026-03-04-new-task/task.json" ]
}

@test "ops: vibe_task add auto-id strips path prefix from title" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '{"schema_version":"v1","tasks":[]}\n' > "$fixture/vibe/registry.json"
  printf '{"schema_version":"v1","worktrees":[]}\n' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task add "docs/plans/2026-03-02-vibe-new-task-flow-convergence.md"
  '
  [ "$status" -eq 0 ]

  local generated_id
  generated_id="$(jq -r '.tasks[0].task_id' "$fixture/vibe/registry.json")"
  [[ "$generated_id" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-2026-03-02-vibe-new-task-flow-convergence$ ]]
  [[ ! "$generated_id" =~ docs-plans ]]
}

@test "ops: vibe_task add auto-id enforces slug max length" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '{"schema_version":"v1","tasks":[]}\n' > "$fixture/vibe/registry.json"
  printf '{"schema_version":"v1","worktrees":[]}\n' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task add "docs/plans/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md"
  '
  [ "$status" -eq 0 ]

  local generated_id suffix
  generated_id="$(jq -r '.tasks[0].task_id' "$fixture/vibe/registry.json")"
  suffix="${generated_id#*-*-*-}"
  [ "${#suffix}" -le 48 ]
}

@test "ops: vibe_task add keeps semantic slash titles when not path-like" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '{"schema_version":"v1","tasks":[]}\n' > "$fixture/vibe/registry.json"
  printf '{"schema_version":"v1","worktrees":[]}\n' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task add "API/Auth token refresh"
  '
  [ "$status" -eq 0 ]

  local generated_id
  generated_id="$(jq -r '.tasks[0].task_id' "$fixture/vibe/registry.json")"
  [[ "$generated_id" =~ api-auth-token-refresh ]]
}

@test "ops: update writes status and next_step to registry" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task update 2026-03-02-rotate-alignment --status in_progress --next-step "New Step"
  '
  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .status' "$fixture/vibe/registry.json")" = "in_progress" ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .next_step' "$fixture/vibe/registry.json")" = "New Step" ]
}

@test "ops: update bind-current syncs worktree binding and cache" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"
  local wt_path="$fixture/wt-test-task"
  mkdir -p "$wt_path"

  run zsh -c '
    cd "'"$wt_path"'"
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task update 2026-03-02-rotate-alignment --bind-current
  '
  [ "$status" -eq 0 ]
  [ "$(jq -r '.worktrees[] | select(.worktree_name=="wt-test-task") | .current_task' "$fixture/vibe/worktrees.json")" = "2026-03-02-rotate-alignment" ]
  [ -f "$wt_path/.vibe/current-task.json" ]
  [ "$(jq -r '.task_id' "$wt_path/.vibe/current-task.json")" = "2026-03-02-rotate-alignment" ]
}

@test "ops: update agent manages git identity" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"
  local git_name_file="$fixture/git_user_name"
  local git_email_file="$fixture/git_user_email"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    git() {
      if [[ "$1" == "rev-parse" ]]; then
        if [[ "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
        if [[ "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
        if [[ "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'"; return 0; fi
      fi
      if [[ "$1" == "config" ]]; then
        if [[ "$2" == "user.name" ]]; then echo "$3" > "'"$git_name_file"'"; return 0; fi
        if [[ "$2" == "user.email" ]]; then echo "$3" > "'"$git_email_file"'"; return 0; fi
      fi
      return 0
    }
    vibe_task update 2026-03-02-rotate-alignment --agent "claude"
  '
  [ "$status" -eq 0 ]
  [ "$(cat "$git_name_file")" = "claude" ]
  [ "$(cat "$git_email_file")" = "claude@vibe.coding" ]
}

@test "ops: remove deletes metadata if unbound" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    git() {
      case "$*" in
        "rev-parse"*) mock_git_registry "'"$fixture"'"; git "$@" ;;
        "branch"*) return 1 ;; # No local branches
        *) return 0 ;;
      esac
    }
    vibe_task remove 2026-03-02-rotate-alignment
  '
  [ "$status" -eq 0 ]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "0" ]
  [ ! -f "$fixture/vibe/tasks/2026-03-02-rotate-alignment/task.json" ]
}

@test "ops: remove fails if bound to a worktree" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_die() { echo "$@"; exit 1; }
    vibe_task remove old-task
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "still bound to a worktree" ]]
}

@test "ops: remove prompts branch cleanup and deletes local+remote when confirmed" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"
  local local_deleted="$fixture/local_deleted"
  local remote_deleted="$fixture/remote_deleted"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    confirm_action() { return 0; }
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        "branch --list"*) echo "  claude/2026-03-02-rotate-alignment"; return 0 ;;
        "branch -r --list"*) echo "  origin/claude/2026-03-02-rotate-alignment"; return 0 ;;
        "branch -d claude/2026-03-02-rotate-alignment") echo local > "'"$local_deleted"'"; return 0 ;;
        "push origin --delete claude/2026-03-02-rotate-alignment") echo remote > "'"$remote_deleted"'"; return 0 ;;
        *) return 0 ;;
      esac
    }
    vibe_task remove 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [ -f "$local_deleted" ]
  [ -f "$remote_deleted" ]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "0" ]
}

@test "ops: remove continues and warns when local branch deletion fails" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    confirm_action() { return 0; }
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        "branch --list"*) echo "  claude/2026-03-02-rotate-alignment"; return 0 ;;
        "branch -r --list"*) return 0 ;;
        "branch -d claude/2026-03-02-rotate-alignment") return 1 ;;
        *) return 0 ;;
      esac
    }
    vibe_task remove 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Branch residue detected" ]]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "0" ]
}

@test "ops: remove succeeds under errexit when no remote branch matches" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    set -e
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        "branch --list"*) return 0 ;;
        "branch -r --list"*) return 0 ;;
        *) return 0 ;;
      esac
    }
    vibe_task remove 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "0" ]
}
