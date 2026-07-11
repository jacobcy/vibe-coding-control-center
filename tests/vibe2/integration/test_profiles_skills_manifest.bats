#!/usr/bin/env bats
# Tests for profiles.sh skills_manifest path output (Issue #1151)

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export VIBE_ROOT="$REPO_ROOT"
  export VIBE_LIB="$REPO_ROOT/lib"
}

@test "minimal profile skills_manifest path is ~/.vibe/skills.json" {
  run zsh -c "
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    get_profile_config minimal
    get_profile_path skills_manifest
  "

  [ "$status" -eq 0 ]
  [ "$output" = "$HOME/.vibe/skills.json" ]
}

@test "github-flow profile skills_manifest path is ~/.vibe/skills.json" {
  run zsh -c "
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    get_profile_config github-flow
    get_profile_path skills_manifest
  "

  [ "$status" -eq 0 ]
  [ "$output" = "$HOME/.vibe/skills.json" ]
}

@test "global profiles use canonical runtime asset paths" {
  run zsh -c "
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    get_profile_config github-flow
    printf '%s\n' \"\$(get_profile_path policies_root)\"
    printf '%s\n' \"\$(get_profile_path prompts_root)\"
  "

  [ "$status" -eq 0 ]
  [[ "$output" == *"$HOME/.vibe/supervisor/policies"* ]]
  [[ "$output" == *"$HOME/.vibe/config/prompts"* ]]
  [[ "$output" != *"assets"* ]]
}

@test "vibe-center profile skills_manifest path is repo-local config/v3/skills.json" {
  run zsh -c "
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    get_profile_config vibe-center
    get_profile_path skills_manifest
  "

  [ "$status" -eq 0 ]
  [ "$output" = "config/v3/skills.json" ]
}

@test "no hard-coded manifests/skills path in profiles.sh" {
  # Regression guard against drift from PR #1130
  run grep -c 'manifests/skills' "$REPO_ROOT/lib/profiles.sh"

  # Exit code should be non-zero (no match found)
  [ "$status" -ne 0 ]
}
