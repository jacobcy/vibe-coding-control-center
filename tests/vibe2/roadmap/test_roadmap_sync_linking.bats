#!/usr/bin/env bats
# tests/roadmap/test_roadmap_sync_linking.bats - PR-to-Issue bridging verification

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

@test "roadmap: bridge_pr_links successfully links merged PR to existing issue" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "project_id": "PVT_project",
  "items": [
    {
      "roadmap_item_id": "gh-125",
      "title": "Fix cleanup logic",
      "source_refs": ["https://github.com/owner/repo/issues/125"],
      "issue_refs": ["gh-125"],
      "github_project_item_id": "PVTI_ISSUE_125"
    }
  ]
}
JSON

  run env FIXTURE="$fixture" zsh -c '
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_store.sh"
    source "$VIBE_LIB/roadmap_issue_intake.sh"

    candidate_json="{\"number\":200,\"title\":\"feat: cleanup registry\",\"body\":\"Fixes #125\",\"url\":\"https://github.com/owner/repo/pull/200\"}"
    _vibe_roadmap_bridge_pr_links "'"$fixture"'/vibe/roadmap.json" "$candidate_json" "owner/repo"
  '

  [ "$status" -eq 0 ]
  
  # Check if the issue item was updated
  local source_refs issue_refs
  source_refs=$(jq -r '.items[0].source_refs | join(",")' "$fixture/vibe/roadmap.json")
  issue_refs=$(jq -r '.items[0].issue_refs | join(",")' "$fixture/vibe/roadmap.json")
  
  [[ "$source_refs" == *"https://github.com/owner/repo/pull/200"* ]]
  [[ "$issue_refs" == *"gh-200"* ]]
  [[ "$issue_refs" == *"gh:owner/repo#200"* ]]
}
