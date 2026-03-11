#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/../.."
  export TMP_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$TMP_HOME/.claude/plugins" "$TMP_HOME/.agents/skills" "$TMP_HOME/.trae/skills" "$TMP_HOME/.kiro/skills"
  mkdir -p "$TMP_HOME/.gemini/antigravity/skills"
  printf '%s\n' '{"plugins":["superpowers@claude-plugins-official"]}' > "$TMP_HOME/.claude/plugins/installed_plugins.json"
  mkdir -p "$TMP_HOME/.agents/skills/brainstorming"

  export TMP_BIN="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$TMP_BIN"
  cat > "$TMP_BIN/npx" <<'SHELL'
#!/usr/bin/env bash
exit 0
SHELL
  chmod +x "$TMP_BIN/npx"
}

@test "vibe skills check is repo-rooted even when run from a subdirectory" {
  run env HOME="$TMP_HOME" PATH="$TMP_BIN:/usr/bin:/bin" bash -lc \
    'cd "'"$REPO_ROOT"'/docs" && HOME="'"$TMP_HOME"'" PATH="'"$TMP_BIN"':/usr/bin:/bin" ../bin/vibe skills check'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "项目级:" ]]
  [[ "$output" =~ "已链接:" ]]
  [[ "$output" =~ "本地 vibe-* skills" ]]
}

@test "global agent symlinks target HOME/.agents/skills for trae and kiro" {
  run env HOME="$TMP_HOME" VIBE_ROOT="$REPO_ROOT" zsh -c '
    source "'"$REPO_ROOT"'/lib/config.sh"
    source "'"$REPO_ROOT"'/lib/skills.sh"
    _vibe_skills_sync_agents_symlinks antigravity trae kiro
    print -r -- "$(readlink "$HOME/.trae/skills/brainstorming")"
    print -r -- "$(readlink "$HOME/.kiro/skills/brainstorming")"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "$TMP_HOME/.agents/skills/brainstorming" ]]
}

@test "global superpowers sync returns failure when npx skills add fails" {
  cat > "$TMP_BIN/npx" <<'SHELL'
#!/usr/bin/env bash
echo "network failure" >&2
exit 7
SHELL
  chmod +x "$TMP_BIN/npx"

  run env HOME="$TMP_HOME" PATH="$TMP_BIN:/usr/bin:/bin" VIBE_ROOT="$REPO_ROOT" bash -lc '
    HOME="'"$TMP_HOME"'" PATH="'"$TMP_BIN"':/usr/bin:/bin" VIBE_ROOT="'"$REPO_ROOT"'" \
      zsh -c '"'"'
        source "'"$REPO_ROOT"'/lib/config.sh"
        source "'"$REPO_ROOT"'/lib/skills.sh"
        _vibe_skills_sync_global_superpowers
      '"'"' 2>&1
  '

  [ "$status" -eq 1 ]
}

@test "workflow and skill docs preserve github project orchestration terminology" {
  run rg -n \
    "roadmap item.*GitHub Project item mirror|Roadmap Item: mirrored GitHub Project item|task.*execution record|Task: execution record" \
    "$REPO_ROOT/.agent/workflows" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe:new-flow.md" ]]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
  [[ "$output" =~ "vibe-task/SKILL.md" ]]
}

@test "task save and check docs treat spec_standard and spec_ref as extension fields" {
  run rg -n \
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

@test "orchestration docs require reading shell output before semantic decisions" {
  run rg -n \
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

@test "handoff governance is defined in a standard and referenced by CLAUDE and skills" {
  run rg -n \
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

@test "patterns define agent auto confirmation without bypassing validation" {
  run rg -n \
    "Auto Confirmation Convention|auto|--yes|过程确认|不得跳过验证|fail-fast|高风险决策" \
    "$REPO_ROOT/.agent/rules/patterns.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Auto Confirmation Convention" ]]
  [[ "$output" =~ "不得跳过验证" ]]
}

@test "vibe-commit docs require task metadata preflight before commit grouping" {
  run rg -n \
    "metadata preflight|current_task|runtime_branch|issue_refs|roadmap_item_ids|spec_standard|spec_ref|hard block|warning" \
    "$REPO_ROOT/.agent/workflows/vibe:commit.md" \
    "$REPO_ROOT/skills/vibe-commit/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "current_task" ]]
  [[ "$output" =~ "runtime_branch" ]]
  [[ "$output" =~ "issue_refs" ]]
  [[ "$output" =~ "roadmap_item_ids" ]]
}

@test "merged pr governance keeps old plans terminal and pushes new work into fresh intake" {
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

@test "issue orchestration defines parent issue scope and out-of-scope split rules" {
  run rg -n \
    "主 issue|sub-issue|超出原范围|新建独立.*issue|治理母题|skill/workflow" \
    "$REPO_ROOT/skills/vibe-issue/SKILL.md" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-issue/SKILL.md" ]]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
}

@test "roadmap intake gate docs define triage ownership without shell auto intake" {
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
