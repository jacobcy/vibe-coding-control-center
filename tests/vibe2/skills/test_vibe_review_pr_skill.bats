#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
}

@test "vibe-review-pr fresh Phase 2 flow activates work after handshake with follow-up SendMessage" {
  run grep -F "fresh spawn 时在 prompt 中直接内嵌 \`phase_1_output\`；不要求额外 SendMessage 才开始" \
    "$REPO_ROOT/skills/vibe-review-pr/SKILL.md"
  [ "$status" -ne 0 ]

  run grep -F "fresh spawn 的 Phase 2 agent 不在初始 prompt 中接收正式审查任务。" \
    "$REPO_ROOT/skills/vibe-review-pr/references/execution-reference.md"
  [ "$status" -eq 0 ]

  run grep -F "初始 prompt 只用于握手，不包含正式审查任务。" \
    "$REPO_ROOT/.claude/agents/pr-code-analyst.md" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md" \
    "$REPO_ROOT/.claude/agents/pr-security-reviewer.md"
  [ "$status" -eq 0 ]

  run grep -F "等待 team-lead 通过 SendMessage 下发首轮正式任务和背景。" \
    "$REPO_ROOT/.claude/agents/pr-code-analyst.md" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md" \
    "$REPO_ROOT/.claude/agents/pr-security-reviewer.md"
  [ "$status" -eq 0 ]
}

@test "vibe-review-pr architect reviewer documentation matches Bash-enabled diff retrieval" {
  run grep -F "tools: Read, Grep, Glob, WebSearch, Bash, SendMessage, ToolSearch" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md"
  [ "$status" -eq 0 ]

  run grep -F "你可以直接使用 Bash 获取所需 diff、提交历史和目标文件内容。" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md"
  [ "$status" -eq 0 ]

  run grep -F "你没有 Bash 工具" \
    "$REPO_ROOT/.claude/agents/pr-architect-reviewer.md"
  [ "$status" -ne 0 ]
}

@test "vibe-review-pr handshake docs and runtime tool allowlists stay aligned" {
  run grep -F "tools: Read, Grep, Glob, Bash, SendMessage, ToolSearch" \
    "$REPO_ROOT/.claude/agents/pr-code-analyst.md" \
    "$REPO_ROOT/.claude/agents/pr-security-reviewer.md"
  [ "$status" -eq 0 ]

  run grep -F "tools: Read, Grep, Glob, WebFetch, Bash, SendMessage, ToolSearch" \
    "$REPO_ROOT/.claude/agents/pr-context-researcher.md"
  [ "$status" -eq 0 ]

  run grep -F "spawn_config:" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F "tools: [Read, Grep, Glob, WebFetch, Bash, SendMessage, ToolSearch]" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F "tools: [Read, Grep, Glob, Bash, SendMessage, ToolSearch]" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F "tools: [Read, Grep, Glob, WebSearch, Bash, SendMessage, ToolSearch]" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]
}

@test "vibe-review-pr result collection and Codex escalation rules stay internally consistent" {
  run grep -F "从 task-notification（status=completed）收集各 agent 报告" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F 'ready_agents = [handshake_status == "ready" 的 agent]' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F "received_agents = [从 task-notification(status=completed) 获取，且属于 ready_agents]" \
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

@test "vibe-review-pr backlog tasks require handshake gates before subagent work counts" {
  run grep -F 'handshake_required: true' \
    "$REPO_ROOT/skills/vibe-review-pr/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F 'on_handshake_failure: "skip_phase_and_fallback_to_single_agent"' \
    "$REPO_ROOT/skills/vibe-review-pr/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F 'on_handshake_failure: "skip_unready_agent_and_mark_review_incomplete"' \
    "$REPO_ROOT/skills/vibe-review-pr/SKILL.md"
  [ "$status" -eq 0 ]

  run grep -F 'step: send_context_handshake' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F 'step: verify_context_handshake' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F '未收到"已就绪" → 标记 context-researcher blocked，停止 Phase 1，并回退到单 agent review' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F '未收到"已就绪" → 标记该 agent blocked，跳过该 agent 的审查结果，并在 Phase 3 标注审查不完整' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F 'fresh spawn 只有在收到"已就绪"后，team-lead 才能把该 teammate 视为有效执行者。' \
    "$REPO_ROOT/skills/vibe-review-pr/references/execution-reference.md"
  [ "$status" -eq 0 ]
}

@test "vibe-review-pr handshake ordering leaves no start-work loophole" {
  run grep -F "【第一步只能握手】" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml" \
    "$REPO_ROOT/skills/vibe-review-pr/references/execution-reference.md"
  [ "$status" -eq 0 ]

  run grep -F "你现在不得开始审查。" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml" \
    "$REPO_ROOT/skills/vibe-review-pr/references/execution-reference.md"
  [ "$status" -eq 0 ]

  run grep -F "你现在不得开始调研。" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml" \
    "$REPO_ROOT/skills/vibe-review-pr/references/execution-reference.md"
  [ "$status" -eq 0 ]

  run grep -F "wait_for_result: true  # 必须等待 Phase 1 完成" \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -ne 0 ]

  run grep -F "  wait: true" \
    "$REPO_ROOT/skills/vibe-review-pr/references/execution-reference.md"
  [ "$status" -ne 0 ]
}

@test "vibe-review-pr activates work only after handshake succeeds" {
  run grep -F 'step: send_context_task' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F 'step: send_code_analyst_task' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F 'step: send_architect_task' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F 'step: send_security_task' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -eq 0 ]

  run grep -F '握手成功后，才通过第二条 SendMessage 下发正式调研任务。' \
    "$REPO_ROOT/skills/vibe-review-pr/references/execution-reference.md"
  [ "$status" -eq 0 ]

  run grep -F 'team-lead 不会预先提供上下文，首轮调研由你自主完成' \
    "$REPO_ROOT/.claude/team-templates/pr-review-team.yaml"
  [ "$status" -ne 0 ]
}
