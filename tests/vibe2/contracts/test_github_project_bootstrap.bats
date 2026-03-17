#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

_make_bootstrap_fixture() {
  local fixture="$1"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "version_goal": "Cutover",
  "items": [
    {
      "roadmap_item_id": "rm-cutover",
      "title": "Cutover",
      "description": null,
      "status": "current",
      "source_type": "github",
      "source_refs": ["gh:owner/repo#90"],
      "issue_refs": ["gh:owner/repo#90"],
      "linked_task_ids": ["task-cutover"],
      "github_project_item_id": null,
      "content_type": null,
      "execution_record_id": "task-cutover",
      "spec_standard": "openspec",
      "spec_ref": "openspec/changes/cutover",
      "created_at": "2026-03-10T12:00:00+0800",
      "updated_at": "2026-03-10T12:00:00+0800"
    }
  ]
}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[
  {"task_id":"task-cutover","title":"Cutover","status":"in_progress","source_type":"local","source_refs":[],"roadmap_item_ids":["rm-cutover"],"issue_refs":[],"pr_ref":null,"related_task_ids":[],"current_subtask_id":null,"subtasks":[],"runtime_worktree_name":null,"runtime_worktree_path":null,"runtime_branch":null,"runtime_agent":null,"assigned_worktree":null,"spec_standard":"openspec","spec_ref":"openspec/changes/cutover","next_step":"apply","created_at":"2026-03-10T12:00:00+0800","updated_at":"2026-03-10T12:00:00+0800","completed_at":null,"archived_at":null}
]}
JSON
  cat > "$fixture/items.json" <<'JSON'
[
  {
    "roadmap_item_id": "rm-cutover",
    "github_project_item_id": "PVTI_cutover",
    "content_type": "issue"
  }
]
JSON
  cat > "$fixture/fields.json" <<'JSON'
[
  {"name":"execution_record_id","type":"text"},
  {"name":"spec_standard","type":"single_select"},
  {"name":"spec_ref","type":"text"}
]
JSON
}

@test "bootstrap contract: field map check passes with required extension fields" {
  local fixture
  fixture="$(mktemp -d)"
  _make_bootstrap_fixture "$fixture"

  run env VIBE_GITHUB_PROJECT_FIELDS_JSON="$fixture/fields.json" zsh scripts/github/project_field_map.sh --check --json

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.status')" = "pass" ]
  [ "$(echo "$output" | jq -r '.extension_fields | length')" = "3" ]
}

@test "bootstrap contract: dry-run reports readiness and proposals" {
  local fixture
  fixture="$(mktemp -d)"
  _make_bootstrap_fixture "$fixture"

  run env \
    VIBE_GITHUB_ROADMAP_FILE="$fixture/vibe/roadmap.json" \
    VIBE_GITHUB_REGISTRY_FILE="$fixture/vibe/registry.json" \
    VIBE_GITHUB_PROJECT_ITEMS_JSON="$fixture/items.json" \
    VIBE_GITHUB_BOOTSTRAP_OUTDIR="$fixture/out" \
    zsh scripts/github/project_bootstrap_sync.sh --dry-run --json

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.audit.readiness.roadmap_missing_github_project_item_id[0]')" = "rm-cutover" ]
  [ "$(echo "$output" | jq -r '.proposals.official_layer_updates[0].after.github_project_item_id')" = "PVTI_cutover" ]
  [ "$(echo "$output" | jq -r '.proposals.extension_layer_writeback[0].spec_standard')" = "openspec" ]
}

@test "bootstrap contract: apply updates roadmap anchors" {
  local fixture
  fixture="$(mktemp -d)"
  _make_bootstrap_fixture "$fixture"

  run env \
    VIBE_GITHUB_ROADMAP_FILE="$fixture/vibe/roadmap.json" \
    VIBE_GITHUB_REGISTRY_FILE="$fixture/vibe/registry.json" \
    VIBE_GITHUB_PROJECT_ITEMS_JSON="$fixture/items.json" \
    VIBE_GITHUB_BOOTSTRAP_OUTDIR="$fixture/out" \
    zsh scripts/github/project_bootstrap_sync.sh --apply --json

  [ "$status" -eq 0 ]
  [ "$(jq -r '.items[0].github_project_item_id' "$fixture/vibe/roadmap.json")" = "PVTI_cutover" ]
  [ "$(jq -r '.items[0].content_type' "$fixture/vibe/roadmap.json")" = "issue" ]
}

@test "bootstrap contract: vibe check bootstrap passes on aligned fixture" {
  local fixture
  fixture="$(mktemp -d)"
  _make_bootstrap_fixture "$fixture"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[{"worktree_name":"wt-cutover","status":"active","tasks":["task-cutover"]}]}
JSON
  tmp="$(mktemp)"
  jq '.items[0].github_project_item_id = "PVTI_cutover" | .items[0].content_type = "issue"' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

  run env VIBE_ROOT="$VIBE_ROOT" zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/check.sh"
    git() {
      case "$*" in
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    vibe_check bootstrap --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.bootstrap.status')" = "pass" ]
}
