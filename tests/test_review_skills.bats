#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/.."
}

@test "review-code local guidance covers working tree and staged diffs" {
  run grep -F "If local: Use \`git diff\` and \`git diff --cached\` for uncommitted changes; use \`git diff main...HEAD\` for committed branch diffs." \
    "$REPO_ROOT/skills/vibe-review-code/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "review-code includes Serena startup and reference checks" {
  run grep -F "uvx --from git+https://github.com/oraios/serena@v0.1.4 serena start-mcp-server" \
    "$REPO_ROOT/skills/vibe-review-code/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "find_referencing_symbols(\"<function_name>\")" \
    "$REPO_ROOT/skills/vibe-review-code/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "bash scripts/serena_gate.sh --base main...HEAD" \
    "$REPO_ROOT/skills/vibe-review-code/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F ".agent/reports/serena-impact.json" \
    "$REPO_ROOT/skills/vibe-review-code/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "review-code uses current LOC threshold" {
  run grep -F "bin/ + lib/ <= 5400 LOC" \
    "$REPO_ROOT/skills/vibe-review-code/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "review-docs local guidance includes unstaged and staged markdown discovery" {
  run grep -F "For local docs review, combine \`git diff --name-only\` and \`git diff --cached --name-only\`, then filter for \`\.md$\`." \
    "$REPO_ROOT/skills/vibe-review-docs/SKILL.md"
  [ "$status" -eq 0 ]
}
