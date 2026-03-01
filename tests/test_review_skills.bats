#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/.."
}

@test "review-code local guidance covers working tree and staged diffs" {
  run grep -F "If local: Use \`git diff\` and \`git diff --cached\` for uncommitted changes; use \`git diff main...HEAD\` for committed branch diffs." \
    "$REPO_ROOT/skills/vibe-review-code/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "review-docs local guidance includes unstaged and staged markdown discovery" {
  run grep -F "For local docs review, combine \`git diff --name-only\` and \`git diff --cached --name-only\`, then filter for \`\.md$\`." \
    "$REPO_ROOT/skills/vibe-review-docs/SKILL.md"
  [ "$status" -eq 0 ]
}
