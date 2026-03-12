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

@test "shared-state: roadmap sync bootstraps missing project ids from source refs and draft fallback" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "project_id": "PVT_project",
  "version_goal": null,
  "items": [
    {
      "roadmap_item_id": "gh-90",
      "title": "Issue backed item",
      "description": null,
      "status": "current",
      "source_type": "github",
      "source_refs": ["gh:owner/repo#90"],
      "issue_refs": ["gh:owner/repo#90"],
      "linked_task_ids": [],
      "github_project_item_id": null,
      "content_type": null,
      "execution_record_id": null,
      "spec_standard": "none",
      "spec_ref": null,
      "created_at": "2026-03-10T12:00:00+0800",
      "updated_at": "2026-03-10T12:30:00+0800"
    },
    {
      "roadmap_item_id": "rm-local",
      "title": "Local draft item",
      "description": "draft body",
      "status": "next",
      "source_type": "local",
      "source_refs": [],
      "issue_refs": [],
      "linked_task_ids": [],
      "github_project_item_id": null,
      "content_type": null,
      "execution_record_id": null,
      "spec_standard": "none",
      "spec_ref": null,
      "created_at": "2026-03-10T12:00:00+0800",
      "updated_at": "2026-03-10T12:30:00+0800"
    }
  ]
}
JSON

  run zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_query.sh"
    source "$VIBE_LIB/roadmap_write.sh"
    _vibe_roadmap_resolve_content_node_id() { echo "CONTENT_90"; return 0; }
    _vibe_roadmap_add_project_item_from_content() { echo "PVTI_issue"; return 0; }
    _vibe_roadmap_create_github_draft_issue() { echo "PVTI_draft"; return 0; }
    _vibe_roadmap_fetch_candidate_repo_issues() { echo "[]"; return 0; }
    _vibe_roadmap_fetch_candidate_repo_prs() { echo "[]"; return 0; }
    _vibe_roadmap_fetch_github_project_items() { cat "'"$fixture"'/vibe/roadmap.json" | jq -c "[.items[] | {github_project_item_id, title, description, content_type, source_type, source_refs, issue_refs, remote_number: null}]"; }
    _vibe_roadmap_sync_github "'"$fixture"'" "owner/repo" "PVT_project"
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.items[0].github_project_item_id' "$fixture/vibe/roadmap.json")" = "PVTI_issue" ]
  [ "$(jq -r '.items[0].content_type' "$fixture/vibe/roadmap.json")" = "issue" ]
  [ "$(jq -r '.items[1].github_project_item_id' "$fixture/vibe/roadmap.json")" = "PVTI_draft" ]
  [ "$(jq -r '.items[1].content_type' "$fixture/vibe/roadmap.json")" = "draft_issue" ]
}

@test "shared-state: roadmap sync adds vibe-task labeled repo issues that are not yet mirrored" {
  local fixture; fixture="$(mktemp -d)"
  local add_log; add_log="$(mktemp)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "project_id": "PVT_project",
  "version_goal": null,
  "items": [
    {
      "roadmap_item_id": "gh-90",
      "title": "Existing mirrored issue",
      "description": null,
      "status": "current",
      "source_type": "github",
      "source_refs": ["gh:owner/repo#90", "https://github.com/owner/repo/issues/90"],
      "issue_refs": ["gh-90"],
      "linked_task_ids": [],
      "github_project_item_id": "PVTI_issue_90",
      "content_type": "issue",
      "execution_record_id": null,
      "spec_standard": "none",
      "spec_ref": null,
      "created_at": "2026-03-10T12:00:00+0800",
      "updated_at": "2026-03-10T12:30:00+0800"
    }
  ]
}
JSON

  run env FIXTURE="$fixture" zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_query.sh"
    source "$VIBE_LIB/roadmap_write.sh"

    _vibe_roadmap_fetch_candidate_repo_issues() {
      cat <<'"'"'JSON'"'"'
[
  {"id":"ISSUE_90","number":90,"title":"Existing mirrored issue","body":"old body","url":"https://github.com/owner/repo/issues/90"},
  {"id":"ISSUE_101","number":101,"title":"New candidate issue","body":"candidate body","url":"https://github.com/owner/repo/issues/101"}
]
JSON
    }

    _vibe_roadmap_fetch_candidate_repo_prs() { echo "[]"; return 0; }

    _vibe_roadmap_add_project_item_from_content() {
      printf "ADD:%s:%s\n" "$1" "$2" >> "'"$add_log"'"
      return 0
    }

    _vibe_roadmap_sync_issue_intake_candidates "'"$fixture"'" "owner/repo" "PVT_project"
  '

  [ "$status" -eq 0 ]
  [ "$(cat "$add_log")" = "ADD:PVT_project:ISSUE_101" ]
}

@test "shared-state: roadmap issue intake fetches with explicit limit and reports gh failures" {
  run zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_issue_intake.sh"

    gh() {
      printf "%s\n" "$*" > "'"$BATS_TEST_TMPDIR"'/gh-args"
      echo "API rate limit exceeded" >&2
      return 1
    }

    vibe_die() {
      echo "VIBE_DIE:$*" >&2
      return 0
    }

    _vibe_roadmap_fetch_candidate_repo_issues "owner/repo"
  '

  [ "$status" -eq 1 ]
  [ "$(cat "$BATS_TEST_TMPDIR/gh-args")" = "issue list --repo owner/repo --state open --label vibe-task --limit 1000 --json id,number,title,body,url" ]
  [[ "$output" =~ "API rate limit exceeded" ]]
  [[ "$output" =~ "VIBE_DIE:Failed to list vibe-task issues for repo 'owner/repo'" ]]
}

@test "shared-state: roadmap pr intake fetches for merged state and reports gh failures" {
  run zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_issue_intake.sh"

    gh() {
      printf "%s\n" "$*" > "'"$BATS_TEST_TMPDIR"'/gh-args-pr"
      echo "API rate limit exceeded" >&2
      return 1
    }

    vibe_die() {
      echo "VIBE_DIE:$*" >&2
      return 0
    }

    _vibe_roadmap_fetch_candidate_repo_prs "owner/repo"
  '

  [ "$status" -eq 1 ]
  [ "$(cat "$BATS_TEST_TMPDIR/gh-args-pr")" = "pr list --repo owner/repo --state merged --limit 1000 --json id,number,title,body,url" ]
  [[ "$output" =~ "API rate limit exceeded" ]]
  [[ "$output" =~ "VIBE_DIE:Failed to list merged PRs for repo 'owner/repo'" ]]
}

@test "shared-state: roadmap refresh updates existing mirrors and imports remote-only items" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "project_id": "PVT_project",
  "version_goal": null,
  "items": [
    {
      "roadmap_item_id": "gh-90",
      "title": "stale title",
      "description": null,
      "status": "current",
      "source_type": "github",
      "source_refs": ["gh:owner/repo#90"],
      "issue_refs": ["gh-90"],
      "linked_task_ids": [],
      "github_project_item_id": "PVTI_issue",
      "content_type": "draft_issue",
      "execution_record_id": null,
      "spec_standard": "none",
      "spec_ref": null,
      "created_at": "2026-03-10T12:00:00+0800",
      "updated_at": "2026-03-10T12:30:00+0800"
    }
  ]
}
JSON

  run zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_query.sh"
    source "$VIBE_LIB/roadmap_write.sh"
    _vibe_roadmap_fetch_github_project_items() {
      cat <<'"'"'JSON'"'"'
[
  {
    "github_project_item_id": "PVTI_issue",
    "title": "fresh issue title",
    "description": "fresh body",
    "content_type": "issue",
    "source_type": "github",
    "source_refs": ["gh:owner/repo#90", "https://github.com/owner/repo/issues/90"],
    "issue_refs": ["gh-90"],
    "remote_number": 90
  },
  {
    "github_project_item_id": "PVTI_draft",
    "title": "remote draft",
    "description": "draft body",
    "content_type": "draft_issue",
    "source_type": "local",
    "source_refs": [],
    "issue_refs": [],
    "remote_number": null
  }
]
JSON
    }
    _vibe_roadmap_refresh_local_mirror "'"$fixture"'" "PVT_project"
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.items[0].title' "$fixture/vibe/roadmap.json")" = "fresh issue title" ]
  [ "$(jq -r '.items[0].content_type' "$fixture/vibe/roadmap.json")" = "issue" ]
  [ "$(jq -r '.items[1].github_project_item_id' "$fixture/vibe/roadmap.json")" = "PVTI_draft" ]
  [ "$(jq -r '.items[1].title' "$fixture/vibe/roadmap.json")" = "remote draft" ]
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
  [ "$(echo "$output" | jq -r '.official_layer.mirrored_items')" = "1" ]
  [ "$(echo "$output" | jq -r '.official_layer.with_github_project_item_id')" = "1" ]
  [ "$(echo "$output" | jq -r '.official_layer.remote_only_imports')" = "0" ]
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
  [[ "$output" == *"GitHub Project Mirror"* ]]
  [[ "$output" == *"Local Execution Bridge"* ]]
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
