#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/roadmap_common.bash"

@test "roadmap contract: sync help describes project-first mirror semantics" {
  run_roadmap_cmd 'vibe_roadmap help'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "GitHub Project item mirror" ]]
  [[ "$output" =~ "compatibility import" ]]
}

@test "roadmap contract: sync --json reports official and extension layers separately" {
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
        *) command git "$@" ;;
      esac
    }
    _vibe_roadmap_sync --provider github --repo owner/repo --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.mode')" = "project_first" ]
  [ "$(echo "$output" | jq -r '.official_layer.provider')" = "github" ]
  [ "$(echo "$output" | jq -r '.extension_layer.writeback')" = "roadmap_bridge_only" ]
}
