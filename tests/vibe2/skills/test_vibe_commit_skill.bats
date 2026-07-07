#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export SKILL="$REPO_ROOT/skills/vibe-commit/SKILL.md"
}

@test "vibe-commit always validates through a temporary commit" {
  run grep -F 'BASE_SHA=$(git rev-parse HEAD)' "$SKILL"
  [ "$status" -eq 0 ]

  run grep -F 'git commit -m "temp: pre-commit validation"' "$SKILL"
  [ "$status" -eq 0 ]

  run grep -F 'git reset --mixed "$BASE_SHA"' "$SKILL"
  [ "$status" -eq 0 ]
}

@test "vibe-commit guards pre-existing graphify changes before cleanup" {
  run grep -F 'GRAPHIFY_DIRTY_BEFORE=$(git status --porcelain -- graphify-out/)' "$SKILL"
  [ "$status" -eq 0 ]

  run grep -F '若 `GRAPHIFY_DIRTY_BEFORE` 非空，禁止自动 restore' "$SKILL"
  [ "$status" -eq 0 ]
}

@test "vibe-commit excludes all graphify artifacts from functional PRs" {
  run grep -F 'PR_BASE=$(git merge-base origin/main HEAD)' "$SKILL"
  [ "$status" -eq 0 ]

  run grep -F 'git diff --name-only "$PR_BASE"..HEAD -- graphify-out/' "$SKILL"
  [ "$status" -eq 0 ]

  run grep -F '普通功能 PR 的上述输出必须为空；非空即 Hard Block' "$SKILL"
  [ "$status" -eq 0 ]

  run grep -F 'Graphify 生成物只进入独立的 `automation/graphify-sync` PR' "$SKILL"
  [ "$status" -eq 0 ]
}

@test "vibe-commit does not describe mixed reset as soft reset" {
  run rg -n '软重置|Soft reset|soft reset' "$SKILL"
  [ "$status" -ne 0 ]
}
