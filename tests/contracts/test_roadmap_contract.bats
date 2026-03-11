#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/roadmap_common.bash"

@test "roadmap contract: sync help describes project mirror and local-only execution semantics" {
  run_roadmap_cmd 'vibe_roadmap help'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Bidirectional GitHub Project mirror sync" ]]
  [[ "$output" =~ "vibe-task-labeled open issues" ]]
  [[ "$output" =~ "task / flow / spec bridge fields stay local" ]]
}

@test "roadmap contract: sync --json infers repo from git and separates local execution fields" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run zsh -c '
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="$VIBE_ROOT/lib"
    source "$VIBE_LIB/config.sh"
    source "$VIBE_LIB/utils.sh"
    source "$VIBE_LIB/roadmap.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "remote get-url origin") echo "git@github.com:owner/repo.git"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    _vibe_roadmap_sync --provider github --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.mode')" = "project_first" ]
  [ "$(echo "$output" | jq -r '.official_layer.provider')" = "github" ]
  [ "$(echo "$output" | jq -r '.official_layer.repo')" = "owner/repo" ]
  [ "$(echo "$output" | jq -r '.official_layer.project_id')" = "PVT_kwDOBHxkss4A1a2B" ]
  [ "$(echo "$output" | jq -r '.local_execution_layer.sync')" = "local_only" ]
}

@test "roadmap contract: classify summary includes title and resulting status" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" 'vibe_roadmap classify rm-1 --status next'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "rm-1" ]]
  [[ "$output" =~ "Alpha" ]]
  [[ "$output" =~ "next" ]]
}
