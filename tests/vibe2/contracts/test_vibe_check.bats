#!/usr/bin/env bats

setup() {
  export PATH="$BATS_TEST_DIRNAME/../../bin:$PATH"
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

@test "vibe check --help returns success" {
  run vibe check --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
  [[ "$output" =~ "roadmap" ]]
  [[ "$output" =~ "task" ]]
  [[ "$output" =~ "flow" ]]
  [[ "$output" =~ "bootstrap" ]]
  [[ "$output" =~ "link" ]]
  [[ "$output" =~ "json <file>" ]]
  [[ "$output" =~ "docs" ]]
}

@test "vibe check check --json returns grouped result" {
  run vibe check check --json
  [[ "$status" -eq 0 || "$status" -eq 1 ]]
  echo "$output" | jq -e '.roadmap and .task and .flow and .bootstrap and .link and .docs' >/dev/null
}

@test "vibe check roadmap --json warns on unlinked roadmap items" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "version_goal": "Ship roadmap links",
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
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/roadmap.sh"
    source "'"$VIBE_ROOT"'/lib/check.sh"
    vibe() {
      local cmd="$1"
      shift
      case "$cmd" in
        roadmap) vibe_roadmap "$@" ;;
        check) vibe_check "$@" ;;
        *) return 1 ;;
      esac
    }
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    vibe_check roadmap --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.roadmap.status')" = "pass" ]
  [ "$(echo "$output" | jq -r '.roadmap.warnings[0]')" = "unlinked roadmap item: rm-1" ]
}

@test "vibe check link --json fails on missing roadmap back-link" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{
  "schema_version": "v2",
  "tasks": [
    {
      "task_id": "task-1",
      "title": "Task One",
      "description": null,
      "status": "todo",
      "source_type": "local",
      "source_refs": [],
      "roadmap_item_ids": ["rm-1"],
      "issue_refs": [],
      "pr_ref": null,
      "related_task_ids": [],
      "current_subtask_id": null,
      "subtasks": [],
      "runtime_worktree_name": null,
      "runtime_worktree_path": null,
      "runtime_branch": null,
      "runtime_agent": null,
      "next_step": null,
      "created_at": "2026-03-08T10:00:00+08:00",
      "updated_at": "2026-03-08T10:00:00+08:00",
      "completed_at": null,
      "archived_at": null
    }
  ]
}
JSON
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "version_goal": "Ship roadmap links",
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
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/check.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    vibe_check link --json
  '

  [ "$status" -eq 1 ]
  [ "$(echo "$output" | jq -r '.link.status')" = "fail" ]
  [ "$(echo "$output" | jq -r '.link.errors[0]')" = "roadmap item missing task back-link: rm-1:task-1" ]
}

@test "vibe task audit --all does not fail-fast when worktrees.json is missing" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    vibe_task audit --all
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Audit Summary Report" ]]
}

@test "vibe check link --json skips runtime worktree existence errors when worktrees.json is missing" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{
  "schema_version": "v2",
  "tasks": [
    {
      "task_id": "task-1",
      "title": "Task One",
      "description": null,
      "status": "in_progress",
      "source_type": "local",
      "source_refs": [],
      "roadmap_item_ids": [],
      "issue_refs": [],
      "pr_ref": null,
      "related_task_ids": [],
      "current_subtask_id": null,
      "subtasks": [],
      "runtime_worktree_name": "wt-runtime",
      "runtime_worktree_path": null,
      "runtime_branch": "task/runtime",
      "runtime_agent": null,
      "next_step": null,
      "created_at": "2026-03-08T10:00:00+08:00",
      "updated_at": "2026-03-08T10:00:00+08:00",
      "completed_at": null,
      "archived_at": null
    }
  ]
}
JSON
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "version_goal": "Ship runtime cleanup",
  "items": []
}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/check.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    vibe_check link --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.link.status')" = "pass" ]
  [ "$(echo "$output" | jq -r '.link.errors | length')" -eq 0 ]
  [ "$(echo "$output" | jq -r '.link.warnings[0]')" = "Missing worktrees.json; skipped runtime worktree existence check" ]
}