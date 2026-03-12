#!/usr/bin/env bats
# tests/roadmap/test_roadmap_sync_intake.bats - PR intake verification tests

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

@test "roadmap: sync_issue_intake_candidates intakes both vibe-task issues and merged PRs" {
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
      "source_refs": ["https://github.com/owner/repo/issues/90"],
      "issue_refs": ["gh-90"],
      "github_project_item_id": "PVTI_issue_90"
    }
  ]
}
JSON

  run env FIXTURE="$fixture" zsh -c '
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_query.sh"
    source "$VIBE_LIB/roadmap_write.sh"
    source "$VIBE_LIB/roadmap_issue_intake.sh"

    _vibe_roadmap_fetch_candidate_repo_issues() {
      cat <<JSON
[
  {"id":"ISSUE_90","number":90,"title":"Existing issue","url":"https://github.com/owner/repo/issues/90"},
  {"id":"ISSUE_101","number":101,"title":"New issue","url":"https://github.com/owner/repo/issues/101"}
]
JSON
    }

    _vibe_roadmap_fetch_candidate_repo_prs() {
      cat <<JSON
[
  {"id":"PR_202","number":202,"title":"Merged PR","url":"https://github.com/owner/repo/pull/202"}
]
JSON
    }

    _vibe_roadmap_add_project_item_from_content() {
      printf "ADD:%s:%s\n" "$1" "$2" >> "'"$add_log"'"
      return 0
    }

    _vibe_roadmap_sync_issue_intake_candidates "'"$fixture"'" "owner/repo" "PVT_project"
  '

  [ "$status" -eq 0 ]
  grep -q "ADD:PVT_project:ISSUE_101" "$add_log"
  grep -q "ADD:PVT_project:PR_202" "$add_log"
  
  # Ensure ISSUE_90 was NOT added again
  [ "$(grep -c "ISSUE_90" "$add_log")" -eq 0 ]
}

@test "roadmap: sync_issue_intake_candidates is idempotent for already mirrored merged PRs" {
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
      "roadmap_item_id": "gh-202",
      "title": "Existing mirrored PR",
      "source_refs": ["https://github.com/owner/repo/pull/202"],
      "issue_refs": ["gh-202"],
      "github_project_item_id": "PVTI_PR_202"
    }
  ]
}
JSON

  run env FIXTURE="$fixture" zsh -c '
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_query.sh"
    source "$VIBE_LIB/roadmap_write.sh"
    source "$VIBE_LIB/roadmap_issue_intake.sh"

    _vibe_roadmap_fetch_candidate_repo_issues() { echo "[]"; }
    _vibe_roadmap_fetch_candidate_repo_prs() {
      cat <<JSON
[
  {"id":"PR_202","number":202,"title":"Existing mirrored PR","url":"https://github.com/owner/repo/pull/202"}
]
JSON
    }

    _vibe_roadmap_add_project_item_from_content() {
      printf "ADD:%s:%s\n" "$1" "$2" >> "'"$add_log"'"
      return 0
    }

    _vibe_roadmap_sync_issue_intake_candidates "'"$fixture"'" "owner/repo" "PVT_project"
  '

  [ "$status" -eq 0 ]
  [ ! -s "$add_log" ]
}
