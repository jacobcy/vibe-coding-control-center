#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export VIBE_ROOT="$REPO_ROOT"
  export VIBE_LIB="$REPO_ROOT/lib"
}

@test "github-flow init copies required claude assets" {
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
  [ -f "$fixture/.claude/settings.json" ]
  [ -f "$fixture/.claude/hooks/block-destructive.sh" ]
  [ -f "$fixture/.claude/hooks/detect-secrets.sh" ]
  [ -f "$fixture/.claude/hooks/protect-files.sh" ]
  [ -f "$fixture/.claude/agents/pr-code-analyst.md" ]
  [ -d "$fixture/.claude/rules" ]
  [ ! -f "$fixture/.claude/rules/coding-standards.md" ]
}

@test "github-flow init exposes vibe workflows and skills to supported agents" {
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
  [ -L "$fixture/.claude/skills/vibe-project-check" ]
  [ -L "$fixture/.codex/skills/vibe-project-check" ]
  [ -L "$fixture/.opencode/skills/vibe-project-check" ]
  [ -L "$fixture/.agent/skills/vibe-project-check" ]
  [ -L "$fixture/.agent/workflows/vibe:new.md" ]
  [ -L "$fixture/.claude/commands/vibe:new.md" ]
}

@test "vibe_init_help explains profile capability differences" {
  run zsh -c "
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/init.sh'
    vibe_init_help 2>&1
  "

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Basic vibe commands" ]]
  [[ "$output" =~ ".agent/ directory" ]]
  [[ "$output" =~ "Flow/task orchestration" ]]
  [[ "$output" =~ "Supervisor orchestration" ]]
}
