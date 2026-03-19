# Vibe Review Health Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

I'm using the writing-plans skill to create the implementation plan.

**Goal:** 重新评估 `codex/roadmap-skill` 当前代码差异，保证 `vibe-review-code` 及周边流程符合硬规则，并把所有 review 检查点、测试、容量问题记录到 GitHub issue 供下个任务跟进。

**Architecture:** 通过层次清晰的 review pipeline（diff → Serena → shell/static checks → tests → issue + skill 调整），以 Shell 真源为中心、Skill 为交互的双层结构，保证审查结论可落地。

**Tech Stack:** Zsh/`bin/lib/scripts`、`bats` 测试、`vibe flow review` + Serena `scripts/serena_gate.sh`、GitHub CLI `gh issue`, `git diff`。

---

### Task 1: 采集差异和影响分析

**Files:** `alias/`, `bin/vibe`, `lib/*.sh`, `scripts/serena_gate.sh`, `skills/vibe-review-code/SKILL.md`, `skills/vibe-roadmap/SKILL.md`

**Step 1: 列出仅含代码目录的 diff 统计**
- Run: `git diff --stat main..HEAD -- alias/ bin/ lib/ scripts/ skills/ tests/`
- Expected: 代码增删变动清晰，输出捕获所有需 review 的文件列表。

**Step 2: 生产 Serena 影响分析**
- Run: `bash scripts/serena_gate.sh --base main...HEAD`
- Expected: 成功生成 `.agent/reports/serena-impact.json`，命令退出码 0；若失败记录消息为 “Serena 启动失败”。

**Step 3: 读取 diff 然后用 `vibe flow review` 对齐 PR 状态**
- Run: `vibe flow review`
- Expected: 收到 Tier1 review 状态（Ready/Blocked），确认当前变更是否已有 open PR。

### Task 2: 校验代码规则与容量

**Files:** `lib/flow*.sh`, `lib/task*.sh`, `lib/roadmap*.sh`, `scripts/tools/metrics.sh`, `skills/vibe-review-code/SKILL.md`

**Step 1: 统计 `bin/ + lib/` 总行数**
- Run:
  ```bash
  python - <<'PY'
from pathlib import Path
paths = list(Path('bin').glob('**/*.sh')) + list(Path('lib').glob('**/*.sh'))
lines = sum(sum(1 for _ in p.open()) for p in paths)
print(lines)
PY
  ```
- Expected: 输出行数≤7000；若>7000，记录“容量超限”并标记需要 raise limit 或拆分。

**Step 2: 查找 `TODO`/`FIXME`/占位符并标注死代码风险**
- Run: `rg -n "TODO|FIXME|PLACEHOLDER" alias bin lib scripts skills`
- Expected: 报告中列出位置，若集中在新代码区需 mark 观察为 Minor 或 Major。

**Step 3: 运行脚本 lint 并捕获安全问题**
- Run: `bash scripts/hooks/lint.sh`
- Expected: 零错误，所有 shellcheck 提示已解决；如报错，记录相关文件/行。

**Step 4: 评估 `skills/vibe-review-code/SKILL.md` 说明是否还可执行**
- Step: 手动对照 CLAUDE/DEVELOPER，确认“LOC limit”更新（7000）等说明无冲突。
- Expected: 找到不一致项后在 review summary 指定修改点（如旧 1200 限制）。

### Task 3: 确认测试与执行质量

**Files:** `tests/test_review_skills.bats`, `tests/test_flow.bats`, `tests/test_metrics.bats`, `tests/test_skills.bats`

**Step 1: 运行关键 bats 测试**
- Run: `bats tests/test_review_skills.bats tests/test_flow.bats tests/test_metrics.bats`
- Expected: 全部 PASS；任何 FAIL 都记录到 review issue 作为 Blocking。

**Step 2: 运行测试型命令（如 `bin/vibe check`）以覆盖 script 入口**
- Run: `bin/vibe check`
- Expected: 返回 “OK” 状态，命令退出码 0；如果失败，记录失败原因。

### Task 4: 生成 issue 并输出审查结论

**Files:** None (use GitHub issue)

**Step 1: 准备 issue 内容（Title, body, checklist）**
- Plan to include: review steps (diff, Serena, LOC limit, TODO check), tests run, issues found, follow-up tasks (documentation, skill update).

**Step 2: 创建 issue**
- Run: `gh issue create --title "Review: roadmap-skill code compliance" --body "- [ ] ..." --label review`
- Expected: issue created successfully; capture issue URL for reference.

**Step 3: 如果发现 `vibe-review-code` 需调整，则更新 issue checklist并 plan 添加相应 task。**

### Task 5: 汇总 Findings 文档

**Files:** `docs/plans/2026-03-07-vibe-review-health-plan.md`（当前文件）或未来 `docs/tasks/` 记录

**Step 1: 记录 Blocking/Major/Minor/Nit 结论**
- Write summary referencing severity, file path, minimal fix.

**Step 2: 告知下一任务需完成什么（issue + plan）**
- Ensure issue describes required fixes (LOC capacity change, skill updates, tests). Once done, issue marks tasks as complete.

---

## Suggested Test Commands Recap
1. `bash scripts/serena_gate.sh --base main...HEAD` (expect JSON report)
2. `bats tests/test_review_skills.bats tests/test_flow.bats tests/test_metrics.bats` (expect PASS)
3. `bash scripts/hooks/lint.sh` (expect no warnings)
4. `bin/vibe check` (expect OK)

## Expected Change Summary (after execution)
- Potential updates to `skills/vibe-review-code/SKILL.md` to clarify token strategy or capacity notes
- GitHub issue created listing review findings and next tasks
- Possibly adjustments in `lib/roadmap*.sh` or `scripts/serena_gate.sh` if blocking issues found
