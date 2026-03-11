#!/usr/bin/env bats
# tests/contracts/test_shared_state_contracts.bats - Shared state schema contract tests

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

_write_roadmap_fixture() {
  local fixture="$1"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "project_id": "PVT_kwDOBHxkss4A1a2B",
  "version_goal": "Q2 sync cutover",
  "items": [
    {
      "roadmap_item_id": "rm-2026-03-10-bootstrap-sync",
      "title": "Bootstrap Sync",
      "description": "Cut over roadmap mirror",
      "status": "current",
      "source_type": "github",
      "source_refs": ["gh:owner/repo#90"],
      "issue_refs": ["gh:owner/repo#90"],
      "linked_task_ids": ["2026-03-10-sync-cutover"],
      "github_project_item_id": "PVTI_xxx",
      "content_type": "issue",
      "execution_record_id": "2026-03-10-sync-cutover",
      "spec_standard": "openspec",
      "spec_ref": "openspec/changes/github-project-sync",
      "created_at": "2026-03-10T12:00:00+0800",
      "updated_at": "2026-03-10T12:30:00+0800"
    }
  ]
}
JSON
}

_write_task_fixture() {
  local fixture="$1"
  mkdir -p "$fixture/vibe/tasks/2026-03-10-sync-cutover" "$fixture/openspec/changes/spec-change"
  cat > "$fixture/vibe/worktrees.json" <<JSON
{
  "schema_version": "v1",
  "worktrees": [
    {
      "worktree_name": "wt-sync-cutover",
      "worktree_path": "$fixture/wt-sync-cutover",
      "branch": "task/sync-cutover",
      "current_task": "2026-03-10-sync-cutover",
      "tasks": ["2026-03-10-sync-cutover"],
      "status": "active",
      "dirty": false
    }
  ]
}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{
  "schema_version": "v1",
  "tasks": [
    {
      "task_id": "2026-03-10-sync-cutover",
      "title": "Sync Cutover",
      "status": "in_progress",
      "source_type": "local",
      "source_refs": [],
      "roadmap_item_ids": ["rm-2026-03-10-bootstrap-sync"],
      "issue_refs": ["gh:owner/repo#90"],
      "pr_ref": null,
      "related_task_ids": [],
      "current_subtask_id": null,
      "subtasks": [],
      "runtime_worktree_name": "wt-sync-cutover",
      "runtime_worktree_path": null,
      "runtime_branch": "task/sync-cutover",
      "runtime_agent": null,
      "assigned_worktree": "wt-sync-cutover",
      "spec_standard": "openspec",
      "spec_ref": "openspec/changes/spec-change",
      "next_step": "Apply cutover",
      "created_at": "2026-03-10T12:00:00+0800",
      "updated_at": "2026-03-10T12:30:00+0800",
      "completed_at": null,
      "archived_at": null
    }
  ]
}
JSON
  cat > "$fixture/vibe/tasks/2026-03-10-sync-cutover/task.json" <<'JSON'
{
  "task_id": "2026-03-10-sync-cutover",
  "title": "Sync Cutover",
  "status": "in_progress",
  "subtasks": [],
  "assigned_worktree": "wt-sync-cutover",
  "spec_standard": "openspec",
  "spec_ref": "openspec/changes/spec-change",
  "next_step": "Apply cutover"
}
JSON
  cat > "$fixture/openspec/changes/spec-change/tasks.md" <<'MD'
- [ ] apply cutover
MD
}

@test "shared-state: roadmap add creates remote project item before writing local mirror" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '{"schema_version":"v2","project_id":"PVT_kwDOBHxkss4A1a2B","version_goal":null,"items":[]}\n' > "$fixture/vibe/roadmap.json"

  run zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_query.sh"
    source "$VIBE_LIB/roadmap_write.sh"
    _vibe_roadmap_create_github_draft_issue() { echo "PVTI_created"; return 0; }
    _vibe_roadmap_add "'"$fixture"'" "Bootstrap GitHub Project mirror"
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.items[0].github_project_item_id' "$fixture/vibe/roadmap.json")" = "PVTI_created" ]
  [ "$(jq -r '.items[0].content_type' "$fixture/vibe/roadmap.json")" = "draft_issue" ]
  [ "$(jq -r '.items[0].execution_record_id' "$fixture/vibe/roadmap.json")" = "null" ]
  [ "$(jq -r '.items[0].spec_standard' "$fixture/vibe/roadmap.json")" = "none" ]
  [ "$(jq -r '.items[0].spec_ref' "$fixture/vibe/roadmap.json")" = "null" ]
}

@test "shared-state: roadmap list/show json preserve github and vibe bridge fields" {
  local fixture; fixture="$(mktemp -d)"
  _write_roadmap_fixture "$fixture"

  run zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_render.sh"
    source "$VIBE_LIB/roadmap_query.sh"
    list_json="$(_vibe_roadmap_list "'"$fixture"'" --json)"
    show_json="$(_vibe_roadmap_show "'"$fixture"'" rm-2026-03-10-bootstrap-sync --json)"
    printf "%s\n%s\n" "$list_json" "$show_json" | jq -sc "{list:.[0],show:.[1]}"
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.list[0].github_project_item_id')" = "PVTI_xxx" ]
  [ "$(echo "$output" | jq -r '.list[0].execution_record_id')" = "2026-03-10-sync-cutover" ]
  [ "$(echo "$output" | jq -r '.show.content_type')" = "issue" ]
  [ "$(echo "$output" | jq -r '.show.spec_standard')" = "openspec" ]
  [ "$(echo "$output" | jq -r '.show.spec_ref')" = "openspec/changes/github-project-sync" ]
}

@test "shared-state: roadmap status json and text distinguish official and extension layers" {
  local fixture; fixture="$(mktemp -d)"
  _write_roadmap_fixture "$fixture"

  run env FIXTURE="$fixture" zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_render.sh"
    source "$VIBE_LIB/roadmap_query.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "$FIXTURE"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    _vibe_roadmap_status --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.official_layer.total_items')" = "1" ]
  [ "$(echo "$output" | jq -r '.official_layer.with_github_project_item_id')" = "1" ]
  [ "$(echo "$output" | jq -r '.sync_check.missing_project_id')" = "0" ]
  [ "$(echo "$output" | jq -r '.extension_layer.with_execution_record_id')" = "1" ]
  [ "$(echo "$output" | jq -r '.extension_layer.with_spec_ref')" = "1" ]

  run env FIXTURE="$fixture" zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_render.sh"
    source "$VIBE_LIB/roadmap_query.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "$FIXTURE"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    _vibe_roadmap_status
  '

  [ "$status" -eq 0 ]
  [[ "$output" == *"GitHub Official Layer"* ]]
  [[ "$output" == *"Vibe Extension Layer"* ]]
}

@test "shared-state: task list and show json preserve execution spec without github identity" {
  local fixture; fixture="$(mktemp -d)"
  _write_task_fixture "$fixture"

  run env FIXTURE="$fixture" zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "$FIXTURE"; return 0 ;;
        "rev-parse --show-toplevel") echo "$FIXTURE"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    list_json="$(vibe_task list --json)"
    show_json="$(vibe_task show 2026-03-10-sync-cutover --json)"
    printf "%s\n%s\n" "$list_json" "$show_json" | jq -sc "{list:.[0],show:.[1]}"
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.list.tasks[0].spec_standard')" = "openspec" ]
  [ "$(echo "$output" | jq -r '.list.tasks[0].spec_ref')" = "openspec/changes/spec-change" ]
  [ "$(echo "$output" | jq -r '.show.spec_standard')" = "openspec" ]
  [ "$(echo "$output" | jq -r '.show.spec_ref')" = "openspec/changes/spec-change" ]
  [ "$(echo "$output" | jq -r '.show.github_project_item_id // "absent"')" = "absent" ]
  [ "$(echo "$output" | jq -r '.show.content_type // "absent"')" = "absent" ]
}

@test "shared-state: worktree records stay runtime-only without github identity" {
  local fixture; fixture="$(mktemp -d)"
  _write_task_fixture "$fixture"

  [ "$(jq -r '.worktrees[0].github_project_item_id // "absent"' "$fixture/vibe/worktrees.json")" = "absent" ]
  [ "$(jq -r '.worktrees[0].content_type // "absent"' "$fixture/vibe/worktrees.json")" = "absent" ]
}
