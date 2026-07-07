#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
}

@test "skills manager scanner reports project Codex skills" {
  local fixture report
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/.codex/skills/codex-only" "$fixture/.agent"

  run bash -c 'cd "'"$fixture"'" && bash "'"$REPO_ROOT"'/skills/vibe-skills-manager/scan-skills.sh" >/dev/null'

  [ "$status" -eq 0 ]
  report="$(find "$fixture/.agent/reports" -name 'skills-state-*.json' -print -quit)"
  [ -n "$report" ]
  jq -e '.project.codex_local.skills[] | select(.name == "codex-only")' "$report"
}
