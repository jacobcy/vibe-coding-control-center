#!/usr/bin/env bats
# Tests for CLAUDE.md template generation (PR #1139 fix verification)

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export VIBE_ROOT="$REPO_ROOT"
  export VIBE_LIB="$REPO_ROOT/lib"
}

@test "vibe_init_help output mentions CLAUDE.md auto-generation for minimal and github-flow" {
  run zsh -c "
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/init.sh'
    vibe_init_help 2>&1
  "

  [ "$status" -eq 0 ]
  [[ "$output" =~ "CLAUDE.md" ]]
  [[ "$output" =~ "minimal" ]]
  [[ "$output" =~ "github-flow" ]]
  [[ "$output" =~ "vibe-center" ]]
}

@test "minimal profile init generates CLAUDE.md with vibe3 flow command" {
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
  [ -f "$fixture/CLAUDE.md" ]

  # Template must use vibe3 flow, not vibe flow
  run grep "vibe3 flow" "$fixture/CLAUDE.md"
  [ "$status" -eq 0 ]

  # Template must NOT have plain "vibe flow" (without vibe3 prefix)
  run grep -E "^\- \`vibe flow\`" "$fixture/CLAUDE.md"
  [ "$status" -ne 0 ]
}

@test "github-flow profile init generates CLAUDE.md with vibe3 flow and vibe3 task commands" {
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
    vibe_init --profile github-flow --yes --skip-labels 2>&1
  "

  [ "$status" -eq 0 ]
  [ -f "$fixture/CLAUDE.md" ]

  # Template must use vibe3 flow and vibe3 task
  run grep "vibe3 flow" "$fixture/CLAUDE.md"
  [ "$status" -eq 0 ]

  run grep "vibe3 task" "$fixture/CLAUDE.md"
  [ "$status" -eq 0 ]

  # Template must NOT have plain "vibe task" (without vibe3 prefix)
  run grep -E "^\- \`vibe task\`" "$fixture/CLAUDE.md"
  [ "$status" -ne 0 ]
}

@test "minimal profile init does not warn about missing AGENTS.md" {
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
  # Intentional behavior: minimal profile does not check for AGENTS.md
  [[ ! "$output" =~ "Missing: AGENTS.md" ]]
}

@test "vibe init output guides users to project check and manager token setup" {
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
  [[ "$output" =~ "/vibe-project-check" ]]
  [[ "$output" =~ "VIBE_MANAGER_GITHUB_TOKEN" ]]
  [[ "$output" =~ "vibe3 serve" ]]
}
