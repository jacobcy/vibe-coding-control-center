#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
}

@test "vibe-review-pr fresh Phase 2 flow uses spawn prompt context instead of mandatory follow-up SendMessage" {
  run grep -F "fresh spawn 时在 prompt 中直接内嵌 \`phase_1_output\`；不要求额外 SendMessage 才开始" \
    "$REPO_ROOT/skills/vibe-review-pr/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "fresh spawn 的 Phase 2 agent 直接从初始 prompt 读取 \`phase_1_output\` 并开始审查。" \
    "$REPO_ROOT/skills/vibe-review-pr/references/execution-reference.md"
  [ "$status" -eq 0 ]

  run grep -F "初次 spawn 审查当前 PR 时，背景已在初始 prompt 中提供；无需等待额外 SendMessage。" \
    "$REPO_ROOT/.claude/agents/pr-code-analyst.md" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md" \
    "$REPO_ROOT/.claude/agents/pr-security-reviewer.md"
  [ "$status" -eq 0 ]

  run grep -F "必须先收到 team-lead 通过 SendMessage 发送的 Phase 1 背景报告。" \
    "$REPO_ROOT/.claude/agents/pr-code-analyst.md" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md" \
    "$REPO_ROOT/.claude/agents/pr-security-reviewer.md"
  [ "$status" -ne 0 ]
}

@test "vibe-review-pr architect reviewer documentation matches Bash-enabled diff retrieval" {
  run grep -F "tools: Read, Grep, Glob, WebSearch, Bash, SendMessage" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md"
  [ "$status" -eq 0 ]

  run grep -F "你可以直接使用 Bash 获取所需 diff、提交历史和目标文件内容。" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md"
  [ "$status" -eq 0 ]

  run grep -F "你没有 Bash 工具" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md"
  [ "$status" -ne 0 ]
}

@test "vibe-review-pr result collection and Codex escalation rules stay internally consistent" {
  run grep -F "从 task-notification（status=completed）收集各 agent 报告" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F "received_agents = [从 task-notification(status=completed) 获取]" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F "第一阶段满足且 Phase 2 完整 → Phase 2.5 保持可选" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml" \
    "$REPO_ROOT/skills/vibe-review-pr/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "第一阶段满足且 Phase 2 不完整 → Phase 2.5 升级为强制" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml" \
    "$REPO_ROOT/skills/vibe-review-pr/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F "仅第一阶段满足 → 跳过 Phase 2.5，直接进入 Phase 3" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -ne 0 ]
}
