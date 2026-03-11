---
name: "vibe:skills"
description: Alias workflow that routes installed-skill management requests to the vibe-skills-manager skill.
category: Workflow
tags: [workflow, vibe, skills, management]
---

# vibe:skills

**Input**: 运行 `/vibe-skills-manager` 触发，启动 Skills 交互式审计流程（扫描 → 诊断 → 推荐 → 确认 → 执行）。

## 定位

- `vibe:skills` 是一个 `alias workflow`。
- 它用于承接已安装 skills 的管理入口，并统一转发到 `vibe-skills-manager` skill。
- 它不负责 repo-local `skills/vibe-*` 的设计或审查。

## Steps

1. 回复用户：`我会把当前请求解释为已安装 skills 管理入口，再委托 vibe-skills-manager skill 处理。`
2. 委托 `skills/vibe-skills-manager/SKILL.md` 执行扫描、诊断、推荐和确认流程。
3. 返回结果或需要用户确认的动作。

## Boundary

- workflow 不承载已安装 skills 的诊断逻辑。
- repo-local `skills/vibe-*` 治理应回到 `vibe-skill-audit`，不在本入口处理。
