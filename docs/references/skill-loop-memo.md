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
  - docs/standards/v2/skill-standard.md
  - docs/standards/v2/skill-trigger-standard.md
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

- `docs/standards/v2/skill-standard.md`
- `docs/standards/v2/skill-trigger-standard.md`
- 各自的 `skills/*/SKILL.md`

## 主链路

`repo issue -> roadmap item -> vibe-new -> vibe-start -> spec execution -> PR -> review/integrate -> done`

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
   - 做什么：旧 flow 到新 flow 的转换器；决定主 issue，判断是否带着未提交改动进入新 flow，还是清空现场后再进入。
   - 不做什么：不创建 task，不直接开始执行。
   - 记忆句：它处理“怎么进入新链”，不是“进来后怎么落 task”。

4. `vibe-start`
   - 做什么：进入新 flow 后，从 issue 落 task，再把 `spec_standard/spec_ref` 交给对应执行体系。
   - 不做什么：不承担旧 flow 到新 flow 的转换，不负责 issue intake。
   - 记忆句：它是“从 issue 落 task 后开始做”，不是“决定切到哪个主 issue”。

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
   - 做什么：task-centered audit；看 task registry、`roadmap <-> task` 映射、task 数据质量、跨 worktree task 总览。
   - 重要纠正：它不是纯只读；在审计修复模式下，可以在用户确认后执行 `vibe task add/update/remove`。
   - 不做什么：不负责 runtime `task <-> flow` 修复。

2. `vibe-check`
   - 做什么：runtime / recovery audit，负责 `task <-> flow`、worktree、stale binding 的现场一致性审计与修复。
   - 重要纠正：它不是 roadmap / task registry 的历史总审计，也不是“下一个做什么”的大脑。
   - 不做什么：不负责 roadmap 排期，不负责 `roadmap <-> task` 语义修复。

## 一句话版本

- `vibe-issue`：发 issue
- `vibe-roadmap`：排 roadmap
- `vibe-new`：旧 flow 到新 flow 的转换，不创建 task
- `vibe-start`：从 issue 落 task，然后开始做
- `vibe-commit`：提交 + PR
- `vibe-integrate`：review / CI / merge readiness
- `vibe-done`：merge and clear
- `vibe-task`：task-centered audit
- `vibe-check`：runtime / recovery audit
