#!/usr/bin/env bats

# Reason: Lock high-risk workflow constraint text that guides agent behavior
# Entry Criterion: §4.1.2 - High-risk commitment text (workflow constraints)
# Alternative Considered: Behavior tests for workflow execution, but text
#                         constraints are the contract definition, not execution

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/../.."
}

@test "doc-text: workflow and skill docs lock github project orchestration terminology" {
  run rg -nH \
    "roadmap item.*GitHub Project item mirror|Roadmap Item: mirrored GitHub Project item|task.*execution record|Task: execution record" \
    "$REPO_ROOT/.agent/workflows" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe:new-flow.md" ]]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
  [[ "$output" =~ "vibe-task/SKILL.md" ]]
}

@test "doc-text: task save and check docs lock spec_standard and spec_ref as extension fields" {
  run rg -nH \
    "spec_standard|spec_ref|扩展桥接字段|extension field|execution spec" \
    "$REPO_ROOT/.agent/workflows/vibe:save.md" \
    "$REPO_ROOT/.agent/workflows/vibe:check.md" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md" \
    "$REPO_ROOT/skills/vibe-save/SKILL.md" \
    "$REPO_ROOT/skills/vibe-check/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "spec_standard" ]]
  [[ "$output" =~ "spec_ref" ]]
}

@test "doc-text: orchestration docs lock shell output reading before semantic decisions" {
  run rg -nH \
    "先读 shell 输出|先运行 `vibe|必须先运行 `vibe|read shell output" \
    "$REPO_ROOT/.agent/workflows/vibe:task.md" \
    "$REPO_ROOT/.agent/workflows/vibe:save.md" \
    "$REPO_ROOT/.agent/workflows/vibe:check.md" \
    "$REPO_ROOT/skills/vibe-issue/SKILL.md" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md" \
    "$REPO_ROOT/skills/vibe-save/SKILL.md" \
    "$REPO_ROOT/skills/vibe-check/SKILL.md" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md"

  [ "$status" -eq 0 ]
}

@test "doc-text: handoff governance standard and references lock handoff constraints" {
  run rg -nH \
    "handoff-governance-standard|task\\.md.*不是.*真源|发现.*不一致.*必须修正" \
    "$REPO_ROOT/docs/standards/handoff-governance-standard.md" \
    "$REPO_ROOT/CLAUDE.md" \
    "$REPO_ROOT/skills/vibe-save/SKILL.md" \
    "$REPO_ROOT/skills/vibe-continue/SKILL.md" \
    "$REPO_ROOT/skills/vibe-commit/SKILL.md" \
    "$REPO_ROOT/skills/vibe-integrate/SKILL.md" \
    "$REPO_ROOT/skills/vibe-done/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "handoff-governance-standard.md" ]]
  [[ "$output" =~ "CLAUDE.md" ]]
}

@test "doc-text: patterns.md locks auto confirmation convention without bypassing validation" {
  run rg -n \
    "Auto Confirmation Convention|auto|--yes|过程确认|不得跳过验证|fail-fast|高风险决策" \
    "$REPO_ROOT/.agent/rules/patterns.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Auto Confirmation Convention" ]]
  [[ "$output" =~ "不得跳过验证" ]]
}

@test "doc-text: vibe-commit docs lock task metadata preflight before commit grouping" {
  run rg -nH \
    "metadata preflight|current_task|runtime_branch|issue_refs|roadmap_item_ids|spec_standard|spec_ref|hard block|warning" \
    "$REPO_ROOT/.agent/workflows/vibe:commit.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe:commit.md" ]]
  [[ "$output" =~ "current_task" ]]
  [[ "$output" =~ "runtime_branch" ]]
  [[ "$output" =~ "issue_refs" ]]
  [[ "$output" =~ "roadmap_item_ids" ]]

  run rg -nH \
    "metadata preflight|current_task|runtime_branch|issue_refs|roadmap_item_ids|spec_standard|spec_ref|hard block|warning" \
    "$REPO_ROOT/skills/vibe-commit/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-commit/SKILL.md" ]]
  [[ "$output" =~ "current_task" ]]
  [[ "$output" =~ "runtime_branch" ]]
  [[ "$output" =~ "issue_refs" ]]
  [[ "$output" =~ "roadmap_item_ids" ]]
}

@test "doc-text: merged pr governance locks old plans terminal and fresh intake rules" {
  run rg -n \
    "merged PR.*terminal|plan.*terminal|新需求.*repo issue|follow-up.*链接|不得.*旧 plan" \
    "$REPO_ROOT/docs/standards/git-workflow-standard.md" \
    "$REPO_ROOT/docs/standards/handoff-governance-standard.md" \
    "$REPO_ROOT/skills/vibe-integrate/SKILL.md" \
    "$REPO_ROOT/skills/vibe-done/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "git-workflow-standard.md" ]]
  [[ "$output" =~ "handoff-governance-standard.md" ]]
  [[ "$output" =~ "vibe-integrate/SKILL.md" ]]
  [[ "$output" =~ "vibe-done/SKILL.md" ]]
}

@test "doc-text: issue orchestration locks parent issue scope and out-of-scope split rules" {
  run rg -n \
    "主 issue|sub-issue|超出原范围|新建独立.*issue|治理母题|skill/workflow" \
    "$REPO_ROOT/skills/vibe-issue/SKILL.md" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-issue/SKILL.md" ]]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
}

@test "doc-text: roadmap intake gate locks triage ownership without shell auto intake" {
  run rg -n \
    "不是所有.*repo issue.*自动进入.*Project|候选资格|vibe-roadmap.*intake gate|vibe-roadmap.*triage|shell.*不负责.*智能.*gate|不自动进入.*GitHub Project" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md" \
    "$REPO_ROOT/skills/vibe-issue/SKILL.md" \
    "$REPO_ROOT/docs/standards/command-standard.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
  [[ "$output" =~ "vibe-issue/SKILL.md" ]]
  [[ "$output" =~ "command-standard.md" ]]
}

@test "doc-text: roadmap intake view locks rejection of local long-term issue cache" {
  run rg -n \
    "repo issue intake 视图|运行时查询.*roadmap mirror|不维护本地长期.*issue.*cache|不维护本地长期.*issue.*registry|triage 决策快照|issue 整池真源" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md" \
    "$REPO_ROOT/docs/standards/command-standard.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
  [[ "$output" =~ "command-standard.md" ]]
}
