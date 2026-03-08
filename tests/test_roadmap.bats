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

@test "roadmap version set-goal writes version_goal to roadmap.json" {
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
    _vibe_roadmap_version set-goal "Ship roadmap split"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Version goal set to: Ship roadmap split" ]]
  [ "$(jq -r '.version_goal' "$fixture/vibe/roadmap.json")" = "Ship roadmap split" ]
}

@test "roadmap version clear-goal clears version_goal in roadmap.json" {
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
    _vibe_roadmap_version clear-goal
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Version goal cleared." ]]
  [ "$(jq -r '.version_goal' "$fixture/vibe/roadmap.json")" = "null" ]
}

@test "roadmap add creates a local roadmap item in roadmap.json" {
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
    vibe_roadmap add "Local roadmap item"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Roadmap item added:" ]]
  [ "$(jq -r '.items[] | select(.title=="Local roadmap item") | .source_type' "$fixture/vibe/roadmap.json")" = "local" ]
}

@test "roadmap list filters items and supports json output" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"
  tmp="$(mktemp)"
  jq '.items[0].linked_task_ids = ["2026-03-08-command-standard-rewrite"]' "$fixture/vibe/roadmap.json" > "$tmp"
  mv "$tmp" "$fixture/vibe/roadmap.json"

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
    vibe_roadmap list --status current --linked --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq 'length')" -eq 1 ]
  [ "$(echo "$output" | jq -r '.[0].roadmap_item_id')" = "rm-1" ]
}

@test "roadmap show returns a single roadmap item as json" {
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
    vibe_roadmap show rm-2 --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.roadmap_item_id')" = "rm-2" ]
  [ "$(echo "$output" | jq -r '.status')" = "p0" ]
  [ "$(echo "$output" | jq -r '.title')" = "Beta" ]
}
