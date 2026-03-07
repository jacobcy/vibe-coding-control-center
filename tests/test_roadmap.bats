#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

make_roadmap_fixture() {
  local fixture="$1"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v2","tasks":[]}
JSON
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version":"v2",
  "version_goal":"Complete shared-state standardization",
  "items":[
    {"roadmap_item_id":"rm-1","title":"Alpha","status":"current","source_type":"local","source_refs":[],"issue_refs":[],"linked_task_ids":[],"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"},
    {"roadmap_item_id":"rm-2","title":"Beta","status":"p0","source_type":"local","source_refs":[],"issue_refs":[],"linked_task_ids":[],"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"},
    {"roadmap_item_id":"rm-3","title":"Gamma","status":"deferred","source_type":"local","source_refs":[],"issue_refs":[],"linked_task_ids":[],"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"}
  ]
}
JSON
}

@test "roadmap status reads roadmap.json instead of registry roadmap block" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/roadmap.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    _vibe_roadmap_status
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Version Goal: Complete shared-state standardization" ]]
  [[ "$output" =~ "P0 (urgent):      1" ]]
  [[ "$output" =~ "Current:          1" ]]
  [[ ! "$output" =~ "Current Version:" ]]
}

@test "roadmap assign writes version_goal to roadmap.json root" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/roadmap.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    _vibe_roadmap_assign "'"$fixture"'" "Ship roadmap split"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Version goal set to: Ship roadmap split" ]]
  [ "$(jq -r '.version_goal' "$fixture/vibe/roadmap.json")" = "Ship roadmap split" ]
}

@test "roadmap classify writes roadmap items into roadmap.json items" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/roadmap.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    _vibe_roadmap_classify "'"$fixture"'" "rm-new" "next"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Issue rm-new classified as: next" ]]
  [ "$(jq -r '.items[] | select(.roadmap_item_id=="rm-new") | .status' "$fixture/vibe/roadmap.json")" = "next" ]
}
