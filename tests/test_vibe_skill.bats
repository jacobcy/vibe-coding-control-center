#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
}

@test "vibe-skill audit flags missing standards references on existing vibe-task skill" {
  run bash "$REPO_ROOT/skills/vibe-skill/scripts/audit-skill-references.sh" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Missing Reference" ]]
  [[ "$output" =~ "docs/standards/glossary.md" ]]
  [[ "$output" =~ "docs/standards/action-verbs.md" ]]
}

@test "vibe-skill audit flags nonexistent vibe command usage" {
  local fixture
  fixture="$(mktemp -d)"

  cat > "$fixture/fake-skill.md" <<'EOF'
---
name: fake-vibe-skill
description: Fake skill for testing
---

# Fake

Run `bin/vibe nonsense launch`.
EOF

  run bash "$REPO_ROOT/skills/vibe-skill/scripts/audit-skill-references.sh" \
    "$fixture/fake-skill.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Capability Gap" ]]
  [[ "$output" =~ "bin/vibe nonsense launch" ]]
}
