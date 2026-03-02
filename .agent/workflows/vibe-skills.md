---
description: 交互式管理、检查、同步和清理 AI Skills。
---

# Vibe Skills

**Input**: 运行 `/vibe-skills` 触发，启动 Skills 交互式审计流程（扫描 → 诊断 → 推荐 → 确认 → 执行）。

## 执行要求

本命令直接对应 `vibe-skills` 技能，你的职责是：
1. **拦截调用**：识别到用户输入 `/vibe-skills` 或类似意图。
2. **委托给 Skill**：直接加载并严格执行 `skills/vibe-skills/SKILL.md` 技能描述的工作流。
3. **互动执行**：遵循该技能规定的步骤，不要自行越过扫描和询问环节，严格执行基于 AI 分析的分步确认流程。
