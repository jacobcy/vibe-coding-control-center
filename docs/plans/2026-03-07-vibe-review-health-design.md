---
title: "Code Review Checklist for Roadmap Skill Collab"
date: "2026-03-07"
status: "draft"
author: "Codex GPT-5"
related_docs:
  - docs/plans/2026-03-05-roadmap-skill-proposal.md
  - skills/vibe-review-code/SKILL.md
  - docs/plans/2026-03-07-noninteractive-shell.md
---

# Review Design: Roadmap Skill + Vibe Review Quality

## Goal
确认 `codex/roadmap-skill` 分支的代码部分在结构、容量、测试与 review 技能上均符合当前硬规则，确保 `vibe-review-code` 仍然可用于最终审查前的质量把关，并把所有实际检查点和后续任务集中记录在 GitHub issue 里供团队追踪。

## Non-Goals
- 不扩展到文档或 changelog 的评审；这部分交给 `view docs` 流程。
- 不立即开发新功能（除非 review 过程中被发现的 blocker 需要立刻修复，另开 issue 处理）。
- 不在本 discussion 中直接合并或推送到 `main`。

## Tech Stack
- Shell/Zsh：所有 CLI 和技能逻辑都运行在 `bin/`, `lib/`, `scripts/`，按 `CLAUDE.md` 要求保持 Shell 作为真源。
- Skills：`skills/vibe-review-code` + `skills/vibe-roadmap` 作为交互流程引擎。
- Testing：`bats` 测试套件在 `tests/` 下，Serena 影响分析在 `scripts/serena_gate.sh`。

## Approach
1. **固定真源**：只查看 `alias/`, `bin/`, `lib/`, `scripts/`, `skills/`, `tests/` 等代码目录的 diff，确认 shell 依旧是执行真源、逻辑未跨层转移。
2. **技术审查**：通过 `vibe-review-code` skill（结合 Serena）审查差异，对照硬限制：LOC（`bin/ + lib/ <= 4800`）、每个函数必须有调用方、无死代码/占位符、测试覆盖、工程化程度。
3. **测试与容量**：跑 `bats tests/test_review_skills.bats`、`tests/test_flow.bats` 等，计算 `bin/`+`lib/` 的行数，判断是否需提升容量预算或压缩代码。
4. **输出 issue**：把 review 检查点、当前状态、未解问题写入新 GitHub issue（标题如“Review: roadmap-skill code compliance”），把我们的 review progress 作为 task list，便于下一任务跟进。
5. **技能评估**：确认 `skills/vibe-review-code/SKILL.md` 的说明不矛盾、推荐子 agent 的提示是否仍然可行，必要时在 issue 中加入“更新 review skill”任务，并在 review summary 里突出需调整的规则。

## Review Tasks (for future execution)
- `git diff main..HEAD -- alias/ bin/ lib/ scripts/ skills/ tests/`（筛选为 review 输入）。
- `bash scripts/serena_gate.sh --base main...HEAD` 产生 `.agent/reports/serena-impact.json`，验证影响分析可用。
- 对 `lib/roadmap*.sh`, `lib/task_audit*.sh`, `skills/vibe-roadmap`, `skills/vibe-review-code` 逐个 audit 是否有 dead code、重复逻辑、超限行数。
- 运行 `sudo`? (No).

## Test Command
- `bats tests/test_review_skills.bats tests/test_flow.bats tests/test_metrics.bats`
- `bash scripts/serena_gate.sh --base main...HEAD`
- `bash -lc 'python - <<"PY"; import os; total=0; ...'` to count lines? (Detailed command to compute `bin/lib` LOC.)

## Expected Result
- 一份 structured review summary（Blocking/Major/Minor/Nit）能指导后续修复。
- `vibe-review-code` skill 说明与实际流程一致，不会误导审查者。
- GitHub issue 记录所有 review 检查点与 follow-up items。
- 如果超过 LOC 预算，issue 中明确是否需要 raise limit or refactor.

## Change Summary (Discussion Only)
- Added: 本文档 1 个（+150 行预估）
- Modified: 0
- Removed: 0
