---
name: "vibe:skills-manager"
description: Skill-backed workflow that routes installed-skill management to the vibe-skills-manager skill.
category: Workflow
tags: [workflow, vibe, skills, management]
---

# vibe:skills-manager

**Input**: 运行 `/vibe-skills-manager` 触发，启动 Skills 交互式审计流程（扫描 -> 诊断 -> 推荐 -> 确认 -> 执行）。

## 定位

- `vibe:skills-manager` 是一个 `skill-backed workflow`。
- 它负责已安装 skills 的 inventory、sync、recommendation 和 cleanup 入口。
- repo-local `skills/vibe-*` 的设计或审查不在这里处理，应交给 `vibe-skill-audit`。

## Steps

1. 回复用户：`我会把当前请求解释为已安装 skills 管理入口，再委托 vibe-skills-manager skill 处理。`
2. 委托 `skills/vibe-skills-manager/SKILL.md` 处理扫描、诊断、推荐和确认流程。
3. 返回结果或需要用户确认的动作。

## Boundary

- workflow 不承载已安装 skills 的诊断与清理逻辑。
- repo-local `skills/vibe-*` 治理应回到 `vibe-skill-audit`。
