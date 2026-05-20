#!/usr/bin/env bats
# Tests for legacy features.skills → local_skills + global_skills migration

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export VIBE_ROOT="$REPO_ROOT"
  export VIBE_LIB="$REPO_ROOT/lib"
}

@test "init warns when existing config has legacy features.skills" {
  local fixture
  fixture="$(mktemp -d)"
  git -C "$fixture" init >/dev/null 2>&1

  # Create a legacy .vibe/config.yaml with old features.skills flag
  mkdir -p "$fixture/.vibe"
  cat > "$fixture/.vibe/config.yaml" <<'YAML'
profile: vibe-center
features:
  agent: true
  skills: true
  supervisor: true
  github_labels: true
  github_orchestration: true
YAML

  # Run vibe init and capture output (use --yes and --skip-labels to avoid prompts)
  run zsh -c "
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile vibe-center --yes --skip-labels 2>&1
  "

  [ "$status" -eq 0 ]
  [[ "$output" =~ "features.skills is deprecated" ]]
}

@test "init generates new format config with local_skills and global_skills" {
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
    vibe_init --profile minimal --yes --skip-labels 2>&1
  "

  [ "$status" -eq 0 ]
  [ -f "$fixture/.vibe/config.yaml" ]

  # New format must have local_skills and global_skills, not features.skills
  run grep "local_skills:" "$fixture/.vibe/config.yaml"
  [ "$status" -eq 0 ]

  run grep "global_skills:" "$fixture/.vibe/config.yaml"
  [ "$status" -eq 0 ]

  # Must NOT have old features.skills key (only local_skills/global_skills)
  run grep -E "^\s+skills:" "$fixture/.vibe/config.yaml"
  [ "$status" -ne 0 ]
}

@test "init does not warn when config already uses new format" {
  local fixture
  fixture="$(mktemp -d)"
  git -C "$fixture" init >/dev/null 2>&1

  # Create a new-format .vibe/config.yaml
  mkdir -p "$fixture/.vibe"
  cat > "$fixture/.vibe/config.yaml" <<'YAML'
profile: minimal
features:
  agent: false
  local_skills: false
  global_skills: false
  supervisor: false
  github_labels: false
  github_orchestration: false
YAML

  run zsh -c "
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile minimal --yes --skip-labels 2>&1
  "

  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "features.skills is deprecated" ]]
}
