#!/usr/bin/env bats
# tests/test_shared_state_contracts.bats - Shared state schema contract tests

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
}

@test "shared-state: roadmap add writes github-project anchor fields by default" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '{"schema_version":"v2","version_goal":null,"items":[]}\n' > "$fixture/vibe/roadmap.json"

  run zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh" 2>/dev/null || true
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/roadmap_query.sh"
    source "$VIBE_LIB/roadmap_write.sh"
    _vibe_roadmap_add "'"$fixture"'" "Bootstrap GitHub Project mirror"
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.items[0].github_project_item_id' "$fixture/vibe/roadmap.json")" = "null" ]
  [ "$(jq -r '.items[0].content_type' "$fixture/vibe/roadmap.json")" = "draft_issue" ]
  [ "$(jq -r '.items[0].execution_record_id' "$fixture/vibe/roadmap.json")" = "null" ]
  [ "$(jq -r '.items[0].spec_standard' "$fixture/vibe/roadmap.json")" = "none" ]
  [ "$(jq -r '.items[0].spec_ref' "$fixture/vibe/roadmap.json")" = "null" ]
}
