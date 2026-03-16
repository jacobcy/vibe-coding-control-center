---
document_type: plan
title: review gated done plan
status: proposed
scope: flow-review-merge-gate
author: Codex GPT-5
created: 2026-03-12
last_updated: 2026-03-12
related_docs:
  - docs/plans/2026-03-12-draft-pr-state-flow-plan.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/git-workflow-standard.md
  - .agent/workflows/vibe:commit.md
  - lib/flow.sh
  - lib/flow_review.sh
---

# Goal

把“`vibe flow done` 前必须存在一份 review 证据，否则不得自动结束 flow”收敛为明确执行计划，避免 agent 在发 PR 后直接快进到 `done`。

# Non-Goals

- 本计划不立即实现 GitHub Rulesets 配置修改。
- 本计划不要求 review 必须来自单一 provider。
- 本计划不把在线 review 缺失直接等同于流程失败；允许 local review + comment 作为降级证据。

# Tech Stack

- Zsh shell CLI
- GitHub Pull Request timeline / review metadata
- GitHub Copilot automatic review
- Codex / Copilot local review CLI

---

## Current Decision

本轮讨论形成以下约定：

1. `vibe flow pr --draft` 是可选草稿发布，不是必经步骤。
2. `vibe flow pr` 是正式提交 PR。
3. `vibe flow done` 不只是关闭 flow；若 PR 尚未 merged，它还必须承担 merge gate。
4. merge 前必须至少存在 **三者之一** 的 review 证据：
   - Copilot 在线 review
   - Codex 在线 review / comment 证据
   - `vibe flow review --local` 结果回贴为 PR comment
5. 只要三者有一，就视为“我们已经完成 review”。
6. 若三者都没有，`vibe flow done` 必须拒绝自动 merge，并提示先完成 review。
7. 若 PR 已经 merged，`vibe flow done` 走向下兼容分支，只做收尾，不重复阻断。

## Recommended Flow

1. `vibe flow new`
2. `vibe flow bind`
3. `vibe flow pr --draft`（可选）
4. `vibe flow pr`
5. GitHub Copilot automatic review 先尝试
6. 若 Copilot 不可用，则 `@codex`
7. 若 Codex 也不可用，则 `vibe flow review --local` 并把结论贴到 PR comment
8. `vibe flow done`
   - 有 review 证据：允许 merge + closeout
   - 无 review 证据：拒绝 done

## Files To Modify

- `lib/flow.sh`
- `lib/flow_review.sh`
- `lib/flow_help.sh`
- `.agent/workflows/vibe:commit.md`
- `skills/vibe-integrate/SKILL.md`
- `tests/flow/test_flow_pr_review.bats`
- `tests/flow/test_flow_bind_done.bats`
- `tests/skills/test_skills.bats`

## Step Tasks

1. 审计现有 `vibe flow pr` / `review` / `done` 帮助和实现，确认哪里最适合承接 merge gate。
2. 为 `done` 增加 review evidence preflight：
   - 已 merged -> 直接兼容收尾
   - 未 merged 且无 review evidence -> 拒绝 done
3. 为 `review` 增加结构化 evidence 查询输出，至少能判断：
   - Copilot 在线 review 是否存在
   - Codex comment / review 证据是否存在
   - local review 回贴 comment 是否存在
4. 更新 workflow / skill 文案，明确“发 PR 不等于可 done，review 是结束前硬门槛”。
5. 用 Bats 锁定：
   - 无 review evidence 时 `done` 失败
   - 任一 evidence 存在时 `done` 可继续
   - 已 merged 时 `done` 不重复卡 gate

# Test Command

```bash
bats tests/flow/test_flow_pr_review.bats
bats tests/flow/test_flow_bind_done.bats
bats tests/skills/test_skills.bats
```

# Expected Result

- agent 不能在发完 PR 后直接 `done`
- `vibe flow done` 成为真正的 merge-before-close gate
- review evidence 允许按 Copilot / Codex / local comment 三选一降级
- 已 merged 的历史 PR 不会被重复阻断

# Change Summary

- Modified: 7-8 files
- Added: 1 file
- Approximate lines: 120-220
