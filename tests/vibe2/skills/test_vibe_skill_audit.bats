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

@test "vibe-skill-audit validates bin vibe commands against the V2 CLI" {
  local fixture
  fixture="$(mktemp -d)"

  cat > "$fixture/fake-skill.md" <<'EOF'
---
name: fake-vibe-skill
description: Fake skill for testing
---

# Fake

Run `bin/vibe keys check`.
EOF

  run bash "$REPO_ROOT/skills/vibe-skill-audit/scripts/audit-skill-references.sh" \
    "$fixture/fake-skill.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "No findings" ]]
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

@test "vibe-skill-audit treats handshake-stage work mixing as blocking" {
  run grep -F "spawn 初始 prompt 必须只包含当前阶段允许动作" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "若在 handshake 阶段混入任何正式工作（如 gh pr view/diff、读取 diff、开始审查、开始调研），视为 Blocking" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "不得在 handshake 阶段混入正式工作" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "把正式工作拆到握手成功后的第二条消息、第二个 task 或后续 phase" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "vibe-skill-audit treats lead pre-investigation as blocking" {
  run grep -F "Lead 最小权限" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "如果显式 PR 入口要求 lead 先 \`gh pr view/diff\`，直接判 Blocking" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "不得要求 lead 在 backlog / 握手前执行 \`gh pr view/diff\` 或 \`git diff/log/show\`" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "lead 预调查：将首个接触 PR / diff 的动作改派给 context/reviewer agent" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "vibe-skill-audit treats fresh-spawn idle fallback as blocking" {
  run grep -F "fresh spawn / 复用分离" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "如果刚握手成功的 fresh spawn agent 被允许进入 idle/待命语义，直接判 Blocking" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "若 fresh spawn agent 在未收到当前任务前被允许“保持空闲/等待新 PR”，视为 Blocking" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "fresh spawn / reuse 混淆：明确“fresh spawn ready 后立即激活当前任务”" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "vibe-skill-audit treats concurrent ready-ready handshake as blocking" {
  run grep -F "握手必须有时序" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F '如果 lead 和 agent 可以同时各说一次“已就绪”而没有 `lead_ready -> agent_ready` 顺序，直接判 Blocking' \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F '并发握手：显式补 `lead_ready -> agent_ready -> send_task` 时序' \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]
}

@test "vibe-skill-audit requires hard backlog metadata gates" {
  run grep -F "backlog gate 可判定" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F '如果只有自然语言约束，没有 `expected_next_action` / `task_activation_allowed` 之类字段，默认视为脆弱设计' \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "若只写“收到 ready 后再做 X”但没有可判定 metadata，视为 Blocking 或至少 High-Risk Drift" \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F '弱 backlog gate：补 `expected_next_action`、`task_activation_allowed`、`activation_state` 等 metadata' \
    "$REPO_ROOT/skills/vibe-skill-audit/SKILL.md"
  [ "$status" -eq 0 ]
}
