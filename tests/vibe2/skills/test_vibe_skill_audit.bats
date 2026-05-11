#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
}

@test "vibe-skill-audit audit passes on existing vibe-task skill" {
  run bash "$REPO_ROOT/skills/vibe-skill-audit/scripts/audit-skill-references.sh" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Drift Warning" || "$output" =~ "No findings" ]]
  [[ "$output" =~ "skills/vibe-task/SKILL.md" ]]
}

@test "vibe-skill-audit audit flags nonexistent vibe command usage" {
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

  run bash "$REPO_ROOT/skills/vibe-skill-audit/scripts/audit-skill-references.sh" \
    "$fixture/fake-skill.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Capability Gap" ]]
  [[ "$output" =~ "bin/vibe nonsense launch" ]]
}

@test "vibe-skill-audit requires workflow gates instead of prompt-only constraints" {
  run grep -F "Gate 优先于提示" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "如关键约束只存在于 prompt 而未落到 gate，必须判为 Blocking 并立即修正" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "不得把关键流程约束只写在 prompt 里" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "backlog task、metadata、状态检查、结果过滤等 gate" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]
}
