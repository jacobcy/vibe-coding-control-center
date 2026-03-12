---
document_type: reference
title: Skill Loop Memo
status: active
scope: skill-loop-summary
authority:
  - non-authoritative-summary
author: Codex GPT-5
created: 2026-03-12
last_updated: 2026-03-12
related_docs:
  - docs/standards/skill-standard.md
  - docs/standards/skill-trigger-standard.md
  - docs/standards/git-workflow-standard.md
  - skills/vibe-issue/SKILL.md
  - skills/vibe-roadmap/SKILL.md
  - skills/vibe-task/SKILL.md
  - skills/vibe-check/SKILL.md
  - skills/vibe-new/SKILL.md
  - skills/vibe-start/SKILL.md
  - skills/vibe-commit/SKILL.md
  - skills/vibe-integrate/SKILL.md
  - skills/vibe-done/SKILL.md
---

# Skill Loop Memo

这是一页速记，不是新的真源。

正式定义看：

- `docs/standards/skill-standard.md`
- `docs/standards/skill-trigger-standard.md`
- 各自的 `skills/*/SKILL.md`

## 主链路

`repo issue -> roadmap item -> plan + task binding -> execute -> PR -> review/integrate -> done`

对应常用 skill：

1. `vibe-issue`
   - 做什么：创建、查重、补模板、润色、落 GitHub issue。
   - 不做什么：不决定 roadmap 排期，不创建 task。
   - 记忆句：它是“发 issue / 整理 issue”的入口，不是“拿 issue 开做”。

2. `vibe-roadmap`
   - 做什么：管理 roadmap item、版本窗口、triage、决定“下一个 roadmap 做什么”。
   - 不做什么：不创建 issue，不修 runtime。
   - 记忆句：它是 roadmap 的大脑。

3. `vibe-new`
   - 做什么：快捷规划入口；决定当前目标从哪里 intake，补 plan，绑定 task，必要时准备逻辑 flow。
   - 不做什么：不直接开始编码。
   - 记忆句：它决定“当前 flow 接下来做什么、按什么 plan 做”，但停在执行前。

4. `vibe-start`
   - 做什么：快捷执行入口；读取当前 flow 已绑定、已有 `spec_standard/spec_ref` 的 task，然后按 plan 开始做。
   - 不做什么：不根据 issue 创建 task，不负责生成 plan。
   - 记忆句：它是“开始做了”，不是“开始想做什么”。

5. `vibe-commit`
   - 做什么：commit 分组、PR 切片、提交并发 PR。
   - 不做什么：不 merge，不收口。
   - 记忆句：它把执行结果送进 PR。

6. `vibe-integrate`
   - 做什么：review、CI、stack 顺序、merge readiness。
   - 不做什么：不直接 close task / issue。
   - 记忆句：它是 review/integrate 阶段。

7. `vibe-done`
   - 做什么：merge and clear；最终收口，关闭 task / issue / flow。
   - 不做什么：不处理新目标，不补业务实现。
   - 记忆句：它是“merge and clear”。

## 审计旁路

这两条不是主交付链，而是审计/修复旁路：

1. `vibe-task`
   - 做什么：task 视角的审计；看 task registry、`roadmap <-> task` 映射、task 数据质量、跨 worktree task 总览。
   - 重要纠正：它不是纯只读；在审计修复模式下，可以在用户确认后执行 `vibe task add/update/remove`。
   - 不做什么：不负责 runtime `task <-> flow` 修复。

2. `vibe-check`
   - 做什么：runtime / 完整性中的“现场一致性”部分，具体是 `task <-> flow`、worktree、stale binding 的审计与修复。
   - 重要纠正：它不是 roadmap / task registry 的历史总审计，也不是“下一个做什么”的大脑。
   - 不做什么：不负责 roadmap 排期，不负责 `roadmap <-> task` 语义修复。

## 一句话版本

- `vibe-issue`：发 issue
- `vibe-roadmap`：排 roadmap
- `vibe-new`：定当前要做什么，并把 plan + task 绑好
- `vibe-start`：开始做
- `vibe-commit`：提交 + PR
- `vibe-integrate`：review / CI / merge readiness
- `vibe-done`：merge and clear
- `vibe-task`：task 账本与映射审计
- `vibe-check`：runtime / binding 审计
