#!/usr/bin/env bats
# Tests for vibe init creating .vibe/settings.yaml override template (Issue #1899)

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export VIBE_ROOT="$REPO_ROOT"
  export VIBE_LIB="$REPO_ROOT/lib"
}

@test "vibe init creates .vibe/settings.yaml template" {
  local fixture
  fixture="$(mktemp -d)"
  git -C "$fixture" init >/dev/null 2>&1

  run zsh -c "
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile github-flow --yes 2>&1
  "

  [ "$status" -eq 0 ]
  [ -f "$fixture/.vibe/settings.yaml" ]
  grep -q "orchestra:" "$fixture/.vibe/settings.yaml"
  grep -q "scene_base_ref:" "$fixture/.vibe/settings.yaml"
}

@test "vibe init does not overwrite existing .vibe/settings.yaml" {
  local fixture
  fixture="$(mktemp -d)"
  git -C "$fixture" init >/dev/null 2>&1

  # Pre-create settings.yaml with custom content
  mkdir -p "$fixture/.vibe"
  echo "# Custom settings" > "$fixture/.vibe/settings.yaml"
  echo "custom: value" >> "$fixture/.vibe/settings.yaml"

  run zsh -c "
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile github-flow --yes 2>&1
  "

  [ "$status" -eq 0 ]
  [ -f "$fixture/.vibe/settings.yaml" ]
  # Content should be unchanged
  grep -q "# Custom settings" "$fixture/.vibe/settings.yaml"
  grep -q "custom: value" "$fixture/.vibe/settings.yaml"
  # Should NOT contain template content
  [[ ! "$(cat "$fixture/.vibe/settings.yaml")" =~ "orchestra:" ]]
}

@test "settings.yaml template contains key override sections" {
  local fixture
  fixture="$(mktemp -d)"
  git -C "$fixture" init >/dev/null 2>&1

  run zsh -c "
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile github-flow --yes 2>&1
  "

  [ "$status" -eq 0 ]
  [ -f "$fixture/.vibe/settings.yaml" ]

  # Check for all required sections
  grep -q "orchestra:" "$fixture/.vibe/settings.yaml"
  grep -q "run:" "$fixture/.vibe/settings.yaml"
  grep -q "plan:" "$fixture/.vibe/settings.yaml"
  grep -q "review:" "$fixture/.vibe/settings.yaml"
}

@test "vibe init creates settings.yaml for vibe-center profile" {
  local fixture
  fixture="$(mktemp -d)"
  git -C "$fixture" init >/dev/null 2>&1

  run zsh -c "
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile vibe-center --yes 2>&1
  "

  [ "$status" -eq 0 ]
  [ -f "$fixture/.vibe/settings.yaml" ]
  grep -q "orchestra:" "$fixture/.vibe/settings.yaml"
  grep -q "scene_base_ref:" "$fixture/.vibe/settings.yaml"
}
