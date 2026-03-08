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
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-04-new-task") | .source_type' "$fixture/vibe/registry.json")" = "local" ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-04-new-task") | .runtime_worktree_name' "$fixture/vibe/registry.json")" = "null" ]
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

@test "ops: update status preserves existing assigned_worktree when not rebinding" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task update old-task --status in_progress
  '
  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="old-task") | .status' "$fixture/vibe/registry.json")" = "in_progress" ]
  [ "$(jq -r '.tasks[] | select(.task_id=="old-task") | .runtime_worktree_name' "$fixture/vibe/registry.json")" = "wt-test-task" ]
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
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .runtime_worktree_name' "$fixture/vibe/registry.json")" = "wt-test-task" ]
}

@test "ops: update accepts --issue/--roadmap-item/--pr and deduplicates refs" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "version_goal": "Test roadmap links",
  "items": [
    {
      "roadmap_item_id": "rm-1",
      "title": "Alpha",
      "description": null,
      "status": "current",
      "source_type": "local",
      "source_refs": [],
      "issue_refs": [],
      "linked_task_ids": [],
      "created_at": "2026-03-08T10:00:00+08:00",
      "updated_at": "2026-03-08T10:00:00+08:00"
    }
  ]
}
JSON

  run env TEST_FIXTURE="$fixture" TEST_HELPER="$HELPER" zsh -c '
    source "$TEST_HELPER"
    setup_task_env
    mock_git_registry "$TEST_FIXTURE"
    vibe_task update 2026-03-02-rotate-alignment \
      --issue gh:owner/repo#68 --issue gh:owner/repo#68 \
      --roadmap-item rm-1 --roadmap-item rm-1 \
      --pr 64
  '
  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .issue_refs | length' "$fixture/vibe/registry.json")" = "1" ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .roadmap_item_ids | length' "$fixture/vibe/registry.json")" = "1" ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .pr_ref' "$fixture/vibe/registry.json")" = "64" ]
  [ "$(jq -r '.items[] | select(.roadmap_item_id=="rm-1") | .linked_task_ids[0]' "$fixture/vibe/roadmap.json")" = "2026-03-02-rotate-alignment" ]
}

@test "ops: update rejects unknown roadmap item without partial write" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "version_goal": "Test roadmap links",
  "items": [
    {
      "roadmap_item_id": "rm-1",
      "title": "Alpha",
      "description": null,
      "status": "current",
      "source_type": "local",
      "source_refs": [],
      "issue_refs": [],
      "linked_task_ids": [],
      "created_at": "2026-03-08T10:00:00+08:00",
      "updated_at": "2026-03-08T10:00:00+08:00"
    }
  ]
}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task update 2026-03-02-rotate-alignment --roadmap-item rm-missing
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Roadmap item not found" ]]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .roadmap_item_ids | length' "$fixture/vibe/registry.json")" = "0" ]
  [ "$(jq -r '.items[] | select(.roadmap_item_id=="rm-1") | .linked_task_ids | length' "$fixture/vibe/roadmap.json")" = "0" ]
}

@test "ops: update maps legacy status names to standard status" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task update 2026-03-02-rotate-alignment --status merged
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .status' "$fixture/vibe/registry.json")" = "completed" ]
}

@test "ops: update agent updates registry without modifying git identity" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"
  local git_name_file="$fixture/git_user_name"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    git() {
      if [[ "$1" == "rev-parse" ]]; then
        if [[ "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
        if [[ "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
        if [[ "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'"; return 0; fi
      fi
      if [[ "$1" == "config" ]]; then
        echo "FAIL: vibe_task should not call git config" > "'"$git_name_file"'"; return 1
      fi
      return 0
    }
    vibe_task update 2026-03-02-rotate-alignment --agent "claude"
  '
  [ "$status" -eq 0 ]
  [ ! -f "$git_name_file" ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .agent' "$fixture/vibe/registry.json")" = "claude" ]
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

@test "ops: remove refuses branch cleanup without --yes" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        "for-each-ref --format=%(refname:short) refs/heads") echo "claude/rotate-alignment"; return 0 ;;
        "for-each-ref --format=%(refname:short) refs/remotes/origin") echo "origin/claude/rotate-alignment"; return 0 ;;
        *) return 0 ;;
      esac
    }
    vibe_task remove 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "rerun with --yes" ]]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "1" ]
}

@test "ops: remove deletes local+remote branches when --yes is provided" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"
  local local_deleted="$fixture/local_deleted"
  local remote_deleted="$fixture/remote_deleted"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        "for-each-ref --format=%(refname:short) refs/heads") echo "claude/rotate-alignment"; return 0 ;;
        "for-each-ref --format=%(refname:short) refs/remotes/origin") echo "origin/claude/rotate-alignment"; return 0 ;;
        "branch -d claude/rotate-alignment") echo local > "'"$local_deleted"'"; return 0 ;;
        "push origin --delete claude/rotate-alignment") echo remote > "'"$remote_deleted"'"; return 0 ;;
        *) return 0 ;;
      esac
    }
    vibe_task remove --yes 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [ -f "$local_deleted" ]
  [ -f "$remote_deleted" ]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "0" ]
}

@test "ops: remove fails when --yes branch cleanup still hits residue" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"; make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        "for-each-ref --format=%(refname:short) refs/heads") echo "claude/rotate-alignment"; return 0 ;;
        "for-each-ref --format=%(refname:short) refs/remotes/origin") return 0 ;;
        "branch -d claude/rotate-alignment") return 1 ;;
        *) return 0 ;;
      esac
    }
    vibe_task remove --yes 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Branch residue detected" ]]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "1" ]
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
        "for-each-ref --format=%(refname:short) refs/heads") return 0 ;;
        "for-each-ref --format=%(refname:short) refs/remotes/origin") return 0 ;;
        *) return 0 ;;
      esac
    }
    vibe_task remove 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "0" ]
}
