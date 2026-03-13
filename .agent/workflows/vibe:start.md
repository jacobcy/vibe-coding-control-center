---
name: "vibe:start"
description: Execution-entry workflow that routes current-flow task execution to the vibe-start skill and stops on missing spec or blockers.
category: Workflow
tags: [workflow, vibe, execution, orchestration]
---

# vibe:start

**Input**: 运行 `/vibe-start`，执行当前 flow 已绑定且带 plan 的 task。

## 定位

- `vibe:start` 是 workflow 层执行入口，只负责判断当前 flow 是否具备可执行 task，并委托 `vibe-start` skill。
- 它默认以 `repo issue -> flow` 作为用户执行主链视角。
- 它负责在当前 flow 中从 issue 落 task 作为 execution bridge，再把 execution spec 交给执行体系。
- 具体 task 选择顺序、`auto` 模式、blocker 分类、handoff 写回，都下沉到 `vibe-start` skill。
- `.agent/context/task.md` 只是 handoff 补充，不是执行图纸。

## Steps

1. 回复用户：`进入执行模式。我会先检查当前 flow 的 task 及其 execution spec，再委托 vibe-start skill 按 plan 执行。`
2. 先读取当前 flow 与 task 事实，确认：
   - 当前 flow 是否绑定 task
   - task 是否具备可解析的 `spec_standard/spec_ref`
   - 若存在 `primary_issue_ref`，它是否已作为当前 task 的主闭环 issue 明确落点
   - 是否存在 `auto` 模式下的后续已绑定 task
3. 委托 `skills/vibe-start/SKILL.md` 处理业务判断：
   - 从 issue 落 task
   - 选择当前 task 或 `auto` 顺序
   - 区分 `issue_refs` 与 `primary_issue_ref`
   - 校验 execution spec
   - 缺 spec 时回退到 `/vibe-new`
   - 无 task 时回退到 `/vibe-task`
   - 必要时继续回退到 `/vibe-roadmap`
4. 只有当前 flow 中可执行的 task 都处理完后，才提示用户进入 `/vibe-commit` 或上游入口。

## Boundary

- workflow 不承载 task 选择顺序、blocker 分类、handoff 结构。
- `vibe:start` 默认按 plan 执行；不得绕过 plan 自由编码。
- 缺少 execution spec 时，停止执行并回退到规划入口，不得在 workflow 中临时补 task。
