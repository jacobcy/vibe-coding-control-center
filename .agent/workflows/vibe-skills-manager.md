---
name: "Vibe: Skills Manager"
description: Interactively manage, audit, sync, recommend, and clean installed AI skills across IDEs; not for authoring or reviewing repo-local `skills/vibe-*`.
category: Workflow
tags: [workflow, vibe, skills, management]
---

# Vibe Skills Manager

**Input**: 运行 `/vibe-skills-manager` 触发，启动 Skills 交互式审计流程（扫描 -> 诊断 -> 推荐 -> 确认 -> 执行）。

## 执行要求

本命令直接对应 `vibe-skills-manager` 技能，你的职责是：
1. **拦截调用**：识别到用户输入 `/vibe-skills-manager` 或类似意图。
2. **委托给 Skill**：直接加载并严格执行 `skills/vibe-skills-manager/SKILL.md` 技能描述的工作流。
3. **互动执行**：遵循该技能规定的步骤，不要自行越过扫描和询问环节，严格执行基于 AI 分析的分步确认流程。
